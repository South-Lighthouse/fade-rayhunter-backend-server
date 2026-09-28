import json
import re
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.utils import timezone as dj_timezone

from ingestion.models import IngestedFile

from .gps import find_nearest_gps, load_gps_points
from .models import MonitoringSession, RayhunterLogEntry

SESSION_ID_RE = re.compile(r"^(\d+)\.ndjson$")

BULK_CREATE_BATCH_SIZE = 1000


def _sensor_dir(sensor):
    return Path(settings.UPLOAD_ROOT) / sensor.slug


def discover_pending_sessions(sensor, limit=None):
    """
    Scans UPLOAD_ROOT/<sensor.slug>/ for `<id>.ndjson` general-log files
    (excluding `<id>-gps.ndjson`) that don't already have a MonitoringSession
    row for this sensor. Returns a list of session_id strings, in filename
    order. This is filesystem-driven rather than IngestedFile-driven, so it
    works whether or not scan_upload_directory has ever run (e.g. local dev
    against data_workbench/ with no webdav pipeline involved).
    """
    sensor_dir = _sensor_dir(sensor)
    if not sensor_dir.is_dir():
        return []

    already_processed = set(
        MonitoringSession.objects.filter(sensor=sensor).values_list("session_id", flat=True)
    )

    session_ids = []
    for entry in sorted(sensor_dir.iterdir()):
        if not entry.is_file():
            continue
        match = SESSION_ID_RE.match(entry.name)
        if not match:
            continue
        session_id = match.group(1)
        if session_id in already_processed:
            continue
        session_ids.append(session_id)
        if limit is not None and len(session_ids) >= limit:
            break

    return session_ids


def _locate_triplet(sensor, session_id):
    sensor_dir = _sensor_dir(sensor)
    general_log_path = sensor_dir / f"{session_id}.ndjson"
    gps_path = sensor_dir / f"{session_id}-gps.ndjson"

    qmdl_gz_path = sensor_dir / f"{session_id}.qmdl.gz"
    qmdl_path = sensor_dir / f"{session_id}.qmdl"
    qmdl_final = qmdl_gz_path if qmdl_gz_path.is_file() else (qmdl_path if qmdl_path.is_file() else None)

    return general_log_path, (gps_path if gps_path.is_file() else None), qmdl_final


def _link_ingested_file(sensor, path):
    """
    Best-effort lookup of the IngestedFile row matching this path, if one
    exists. relative_path is relative to UPLOAD_ROOT and starts with the
    sensor slug (see ingestion/tasks.py). Returns None if no such row exists
    -- normal in local dev, where scan_upload_directory may never have run.
    """
    if path is None:
        return None
    relative_path = str(path.relative_to(settings.UPLOAD_ROOT))
    return IngestedFile.objects.filter(sensor=sensor, relative_path=relative_path).first()


def _parse_packet_timestamp(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


def _severity_and_message(events):
    """
    events is the header-aligned list from a general-log line; a non-null
    entry means that analyzer triggered. Multiple simultaneous triggers are
    rare but possible -- join their messages and keep the highest severity.
    """
    severity_rank = {
        RayhunterLogEntry.SEVERITY_INFORMATIONAL: 0,
        RayhunterLogEntry.SEVERITY_LOW: 1,
        RayhunterLogEntry.SEVERITY_MEDIUM: 2,
        RayhunterLogEntry.SEVERITY_HIGH: 3,
    }
    triggered = [e for e in (events or []) if e]
    if not triggered:
        return None, None

    best_severity = max((e.get("event_type") for e in triggered), key=lambda s: severity_rank.get(s, -1))
    message = "; ".join(e.get("message", "") for e in triggered)
    return best_severity, message


def process_session(sensor, session_id):
    """
    Parses one monitoring session's general log (+ correlated GPS) into a
    MonitoringSession and its RayhunterLogEntry rows. Idempotent: if a
    MonitoringSession already exists for (sensor, session_id), it's returned
    unchanged rather than reprocessed.

    Returns the MonitoringSession. Raises ValueError if the general log file
    is missing (nothing to parse) or its header can't be read.
    """
    existing = MonitoringSession.objects.filter(sensor=sensor, session_id=session_id).first()
    if existing is not None:
        return existing

    general_log_path, gps_path, qmdl_path = _locate_triplet(sensor, session_id)
    if not general_log_path.is_file():
        raise ValueError(f"general log not found: {general_log_path}")

    gps_points = load_gps_points(gps_path)

    with general_log_path.open() as fh:
        header_line = fh.readline()
        try:
            header = json.loads(header_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"unreadable header in {general_log_path}: {exc}") from exc

        session = MonitoringSession.objects.create(
            sensor=sensor,
            session_id=session_id,
            rayhunter_version=header.get("rayhunter", {}).get("rayhunter_version", ""),
            system_os=header.get("rayhunter", {}).get("system_os", ""),
            arch=header.get("rayhunter", {}).get("arch", ""),
            report_version=header.get("report_version"),
            analyzers=header.get("analyzers", []),
            has_gps=bool(gps_points),
            general_log_file=_link_ingested_file(sensor, general_log_path),
            gps_log_file=_link_ingested_file(sensor, gps_path) if gps_path else None,
            qmdl_file=_link_ingested_file(sensor, qmdl_path) if qmdl_path else None,
        )

        batch = []
        for line_number, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            qmdl_ts = _parse_packet_timestamp(record.get("packet_timestamp"))
            severity, message = _severity_and_message(record.get("events"))
            is_alert = severity is not None
            if not is_alert:
                message = record.get("skipped_message_reason") or ""

            gps_point = None
            if qmdl_ts is not None:
                gps_point = find_nearest_gps(gps_points, int(qmdl_ts.timestamp()))

            batch.append(
                RayhunterLogEntry(
                    session=session,
                    sensor=sensor,
                    line_number=line_number,
                    qmdl_timestamp=qmdl_ts,
                    gps_timestamp=(
                        datetime.fromtimestamp(gps_point["system_time"], tz=timezone.utc)
                        if gps_point
                        else None
                    ),
                    latitude=gps_point["lat"] if gps_point else None,
                    longitude=gps_point["lon"] if gps_point else None,
                    is_alert=is_alert,
                    severity=severity or "",
                    log_entry=message,
                    raw_payload=record,
                )
            )
            if len(batch) >= BULK_CREATE_BATCH_SIZE:
                RayhunterLogEntry.objects.bulk_create(batch)
                batch = []

        if batch:
            RayhunterLogEntry.objects.bulk_create(batch)

    session.processed_at = dj_timezone.now()
    session.save(update_fields=["processed_at"])

    for ingested_file in (session.general_log_file, session.gps_log_file, session.qmdl_file):
        if ingested_file is not None:
            ingested_file.status = IngestedFile.STATUS_DONE
            ingested_file.processed_at = dj_timezone.now()
            ingested_file.save(update_fields=["status", "processed_at"])

    return session
