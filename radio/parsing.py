import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings
from django.utils import timezone as dj_timezone

from captures.models import MonitoringSession
from ingestion.models import IngestedFile

from .decode_timing_advance import decode_timing_advance_hex
from .ek_flatten import flatten_packet, is_noise, short
from .models import RadioCapture, RadioPacket
from .packet_type import GSMTAP_TYPE_MAC_RACH_RESPONSE, derive_packet_type

BULK_CREATE_BATCH_SIZE = 150

_LOOKUP_PATH = Path(__file__).resolve().parent / "raw_path_lookup.json"
with _LOOKUP_PATH.open() as _fh:
    RAW_PATH_LOOKUP = json.load(_fh)  # django_name -> raw ek path

_RAW_PATH_TO_DJANGO_NAME = {v: k for k, v in RAW_PATH_LOOKUP.items()}
_PROMOTED_RAW_PATHS = set(RAW_PATH_LOOKUP.values())
_FIELD_BY_DJANGO_NAME = {name: RadioPacket._meta.get_field(name) for name in RAW_PATH_LOOKUP}

_FRACTIONAL_SECONDS_RE = re.compile(r"\.(\d{6})\d+")


def discover_pending_captures(sensor=None, limit=None):
    """
    Finds MonitoringSessions whose qmdl_file was left at
    STATUS_AWAITING_FURTHER_PROCESSING by captures.parsing.process_session
    and that don't have a RadioCapture yet. Optionally scoped to one sensor
    and/or capped at `limit` rows.
    """
    qs = (
        MonitoringSession.objects.filter(
            qmdl_file__status=IngestedFile.STATUS_AWAITING_FURTHER_PROCESSING,
            radio_capture__isnull=True,
        )
        .select_related("sensor", "qmdl_file", "gps_log_file")
        .order_by("id")
    )
    if sensor is not None:
        qs = qs.filter(sensor=sensor)
    if limit is not None:
        qs = qs[:limit]
    return list(qs)


def _parse_frame_time(value):
    if not value:
        return None
    value = value.replace("Z", "+00:00")
    # tshark emits 9-digit (nanosecond) fractional seconds; datetime.fromisoformat
    # only reliably accepts up to 6 (microsecond) -- truncate the rest.
    value = _FRACTIONAL_SECONDS_RE.sub(r".\1", value)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_gps_comment(pkt_comment_layer):
    """
    pkt_comment_layer is `layers.get("pkt_comment")` -- the pcapng Enhanced
    Packet Block comment tshark exposes under its own synthetic layer, which
    is where tools/qmdl2pcap embeds the matched GPS point (see
    lib/src/pcap.rs's GsmtapPcapWriter::write_gsmtap_message). Note this is
    NOT reachable via `-T ek`'s normal per-protocol field flattening --
    verified separately against a real GPS-embedded capture.
    """
    if not pkt_comment_layer:
        return None, None, None
    comments = pkt_comment_layer if isinstance(pkt_comment_layer, list) else [pkt_comment_layer]
    for comment in comments:
        if not isinstance(comment, dict):
            continue
        raw = comment.get("frame_frame_comment")
        if not raw:
            continue
        try:
            gps = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        unix_ts = gps.get("unix_ts")
        gps_timestamp = None
        if unix_ts is not None:
            try:
                gps_timestamp = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
            except (OSError, OverflowError, ValueError):
                # qmdl2pcap (and upstream Rayhunter, which it mirrors) can
                # emit a sentinel unix_ts for a GPS fix that predates any
                # packet correlation -- fixed at the source, but tolerate it
                # here too for already-generated pcaps and any other garbage
                # that slips through. lat/lon are still real, so keep those.
                gps_timestamp = None
        return gps_timestamp, gps.get("lat"), gps.get("lon")
    return None, None, None


def _coerce_value(django_name, value):
    field = _FIELD_BY_DJANGO_NAME[django_name]
    if field.get_internal_type() == "BigIntegerField":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
    text = str(value)
    return text[: field.max_length] if field.max_length else text


def _build_packet(capture, sensor, layers):
    gsmtap = layers.get("gsmtap") or {}
    gsmtap_type = gsmtap.get("gsmtap_gsmtap_type")

    qmdl_timestamp = _parse_frame_time((layers.get("frame") or {}).get("frame_frame_time_epoch"))
    gps_timestamp, latitude, longitude = _parse_gps_comment(layers.get("pkt_comment"))

    timing_advance = None
    if gsmtap_type == GSMTAP_TYPE_MAC_RACH_RESPONSE:
        data_layer = layers.get("data") or {}
        if isinstance(data_layer, list):
            data_layer = data_layer[0] if data_layer else {}
        raw_hex = data_layer.get("data_data_data")
        if raw_hex:
            timing_advance = decode_timing_advance_hex(raw_hex)

    flat = flatten_packet(layers)

    column_values = {}
    raw_fields = {}
    for raw_path, values in flat.items():
        django_name = _RAW_PATH_TO_DJANGO_NAME.get(raw_path)
        if django_name is not None:
            column_values[django_name] = _coerce_value(django_name, values[0])
            continue
        if is_noise(raw_path):
            continue
        raw_fields[short(raw_path)] = values[0] if len(values) == 1 else values

    return RadioPacket(
        capture=capture,
        sensor=sensor,
        qmdl_timestamp=qmdl_timestamp,
        gps_timestamp=gps_timestamp,
        latitude=latitude,
        longitude=longitude,
        packet_type=derive_packet_type(layers, gsmtap_type),
        timing_advance=timing_advance,
        raw_fields=raw_fields,
        **column_values,
    )


def _run_qmdl2pcap(qmdl_path, gps_path, pcap_path):
    cmd = [settings.QMDL2PCAP_BIN, str(qmdl_path)]
    if gps_path is not None:
        cmd += ["--gps", str(gps_path)]
    cmd += ["-o", str(pcap_path)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def _parse_pcap(capture, sensor, pcap_path):
    proc = subprocess.run(
        ["tshark", "-r", str(pcap_path), "-T", "ek"], check=True, capture_output=True, text=True
    )
    batch = []
    count = 0
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith('{"index"'):
            continue
        try:
            pkt = json.loads(line)
        except json.JSONDecodeError:
            continue
        batch.append(_build_packet(capture, sensor, pkt.get("layers", {})))
        count += 1
        if len(batch) >= BULK_CREATE_BATCH_SIZE:
            RadioPacket.objects.bulk_create(batch)
            batch = []
    if batch:
        RadioPacket.objects.bulk_create(batch)
    return count


def process_capture(session):
    """
    Converts one MonitoringSession's QMDL (+ GPS) into a PCAP via
    tools/qmdl2pcap, then parses it with `tshark -T ek` into RadioPacket
    rows. Idempotent: if the session already has a RadioCapture, returns it
    unchanged rather than reprocessing.

    Unlike captures.parsing.process_session, failures here are recorded on
    the RadioCapture row (status="error") rather than raised -- the pipeline
    deals with many packets' worth of subprocess/parse risk per session, and
    one bad session (corrupt QMDL, tshark crash) shouldn't block the batch.
    Returns the RadioCapture either way; callers check `.status`.
    """
    existing = getattr(session, "radio_capture", None)
    if existing is not None:
        return existing

    qmdl_file = session.qmdl_file
    if qmdl_file is None:
        raise ValueError(f"session has no qmdl_file recorded: {session}")

    qmdl_path = Path(settings.UPLOAD_ROOT) / qmdl_file.relative_path
    if not qmdl_path.is_file():
        raise ValueError(f"qmdl file not found on disk: {qmdl_path}")

    gps_path = None
    if session.gps_log_file is not None:
        candidate = Path(settings.UPLOAD_ROOT) / session.gps_log_file.relative_path
        if candidate.is_file():
            gps_path = candidate

    capture = RadioCapture.objects.create(session=session, status=RadioCapture.STATUS_PENDING)

    pcap_dir = Path(settings.RADIO_PCAP_ROOT) / session.sensor.slug
    pcap_dir.mkdir(parents=True, exist_ok=True)
    pcap_path = pcap_dir / f"{session.session_id}.pcapng"

    try:
        _run_qmdl2pcap(qmdl_path, gps_path, pcap_path)
        packet_count = _parse_pcap(capture, session.sensor, pcap_path)
    except Exception as exc:
        # Broad on purpose: this is the batch-isolation boundary (see
        # docstring above) -- a subprocess failure, a parsing bug tripped by
        # one session's unusual data, or anything else must not take down
        # the whole run. subprocess.CalledProcessError gets its stderr/stdout
        # surfaced; anything else just gets str(exc).
        if isinstance(exc, subprocess.CalledProcessError):
            error_output = exc.stderr or exc.stdout or str(exc)
        else:
            error_output = str(exc)
        capture.status = RadioCapture.STATUS_ERROR
        capture.error_message = error_output[:4000]
        capture.processed_at = dj_timezone.now()
        capture.save(update_fields=["status", "error_message", "processed_at"])
        return capture

    capture.status = RadioCapture.STATUS_DONE
    capture.pcap_path = str(pcap_path.relative_to(settings.RADIO_PCAP_ROOT))
    capture.packet_count = packet_count
    capture.processed_at = dj_timezone.now()
    capture.save(update_fields=["status", "pcap_path", "packet_count", "processed_at"])

    for ingested_file in (qmdl_file, session.gps_log_file):
        if ingested_file is not None:
            ingested_file.status = IngestedFile.STATUS_DONE
            ingested_file.processed_at = dj_timezone.now()
            ingested_file.save(update_fields=["status", "processed_at"])

    return capture
