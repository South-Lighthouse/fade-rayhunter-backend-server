from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Max
from django.db.models.functions import TruncDate
from django.utils import timezone

from ingestion.models import IngestedFile
from telemetry.models import TelemetryRecord

STATUS_OK = "ok"
STATUS_STALE = "stale"
STATUS_NEVER = "never"

STATUS_LABELS = {
    STATUS_OK: "OK",
    STATUS_STALE: "Stale",
    STATUS_NEVER: "Never reported",
}


def annotate_pulse(sensor_qs, stale_hours):
    """
    Annotates each sensor in the queryset with last_upload, last_telemetry,
    last_seen, hours_since_seen and a status ("ok" / "stale" / "never").

    Two Max() aggregates in a single query rather than per-sensor lookups,
    so this stays cheap regardless of sensor count.
    """
    sensors = list(
        sensor_qs.annotate(
            last_upload=Max("ingested_files__uploaded_at"),
            last_telemetry=Max("telemetry__received_at"),
        )
    )

    now = timezone.now()
    threshold = timedelta(hours=stale_hours)

    for sensor in sensors:
        candidates = [t for t in (sensor.last_upload, sensor.last_telemetry) if t is not None]
        last_seen = max(candidates) if candidates else None
        sensor.last_seen = last_seen

        if last_seen is None:
            sensor.status = STATUS_NEVER
            sensor.hours_since_seen = None
        else:
            age_hours = (now - last_seen).total_seconds() / 3600
            sensor.hours_since_seen = age_hours
            sensor.status = STATUS_OK if age_hours <= stale_hours else STATUS_STALE

        sensor.status_label = STATUS_LABELS[sensor.status]

    return sensors


def _daily_counts(queryset, timestamp_field, since):
    rows = (
        queryset.filter(**{f"{timestamp_field}__gte": since})
        .annotate(day=TruncDate(timestamp_field))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count")
    )
    return dict(rows)


def merged_daily_series(sensor_ids, days):
    """
    Aggregate upload + telemetry daily counts across one or more sensors for
    the trailing `days` days (inclusive of today). Returns two aligned lists
    of (date, count) tuples: (upload_series, telemetry_series).
    """
    since = timezone.now() - timedelta(days=days - 1)
    since_date = since.date()

    upload_counts = _daily_counts(
        IngestedFile.objects.filter(sensor_id__in=sensor_ids), "uploaded_at", since
    )
    telemetry_counts = _daily_counts(
        TelemetryRecord.objects.filter(sensor_id__in=sensor_ids), "received_at", since
    )

    all_days = [since_date + timedelta(days=i) for i in range(days)]
    upload_series = [(d, upload_counts.get(d, 0)) for d in all_days]
    telemetry_series = [(d, telemetry_counts.get(d, 0)) for d in all_days]
    return upload_series, telemetry_series


def sensor_timeline_events(sensor, days, limit=200):
    """
    Merged, most-recent-first timeline of this sensor's ingested files and
    telemetry records over the trailing `days` days.
    """
    since = timezone.now() - timedelta(days=days)

    events = []
    for f in sensor.ingested_files.filter(uploaded_at__gte=since).order_by("-uploaded_at")[:limit]:
        events.append(
            {
                "timestamp": f.uploaded_at,
                "kind": "upload",
                "detail": f.filename,
                "extra": f"{f.file_size or 0} bytes · {f.get_status_display()}",
            }
        )
    for t in sensor.telemetry.filter(received_at__gte=since).order_by("-received_at")[:limit]:
        events.append(
            {
                "timestamp": t.received_at,
                "kind": "telemetry",
                "detail": t.event_type or "(no type)",
                "extra": t.message,
            }
        )

    events.sort(key=lambda e: e["timestamp"], reverse=True)
    return events[:limit]


def dashboard_groups(stale_hours, trend_days=14):
    """
    All sensors, annotated with pulse info and grouped by country (plus an
    "Unassigned" group for sensors with no country set), each with its own
    trend series for the country-level chart on the dashboard.
    """
    from sensors.models import Country, Sensor

    all_sensors = annotate_pulse(
        Sensor.objects.select_related("sensor_type", "country"), stale_hours
    )

    by_country_id = defaultdict(list)
    for sensor in all_sensors:
        by_country_id[sensor.country_id].append(sensor)

    groups = []
    for country in Country.objects.order_by("name"):
        sensors = by_country_id.get(country.id, [])
        upload_series, _ = merged_daily_series([s.id for s in sensors], trend_days) if sensors else ([], [])
        groups.append({"country": country, "sensors": sensors, "trend_series": upload_series})

    unassigned = by_country_id.get(None, [])
    if unassigned:
        upload_series, _ = merged_daily_series([s.id for s in unassigned], trend_days)
        groups.append({"country": None, "sensors": unassigned, "trend_series": upload_series})

    return groups
