from collections import defaultdict
from datetime import datetime, time

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from ingestion.models import IngestedFile
from telemetry.models import TelemetryRecord

from .pulse import STATUS_LABELS, annotate_pulse


def build_country_report(country, start_date, end_date, stale_hours):
    """
    start_date/end_date: date objects, inclusive range.

    Returns a plain dict consumed by both the admin report view and the
    generate_country_report management command — the single source of
    truth for the report's content either way.
    """
    range_start = timezone.make_aware(datetime.combine(start_date, time.min))
    range_end = timezone.make_aware(datetime.combine(end_date, time.max))

    sensors = country.sensors.select_related("sensor_type").order_by("name")
    pulses = annotate_pulse(sensors, stale_hours)

    rows = []
    daily_uploads = defaultdict(int)

    for sensor in pulses:
        uploads_qs = IngestedFile.objects.filter(sensor=sensor, uploaded_at__range=(range_start, range_end))
        upload_count = uploads_qs.count()
        total_bytes = uploads_qs.aggregate(total=Sum("file_size"))["total"] or 0
        telemetry_count = TelemetryRecord.objects.filter(
            sensor=sensor, received_at__range=(range_start, range_end)
        ).count()

        for day, count in (
            uploads_qs.annotate(day=TruncDate("uploaded_at")).values("day").annotate(count=Count("id")).values_list(
                "day", "count"
            )
        ):
            daily_uploads[day] += count

        rows.append(
            {
                "sensor": sensor,
                "upload_count": upload_count,
                "total_bytes": total_bytes,
                "telemetry_count": telemetry_count,
                "status": sensor.status,
                "status_label": STATUS_LABELS[sensor.status],
                "last_seen": sensor.last_seen,
            }
        )

    daily_series = sorted(daily_uploads.items())

    return {
        "country": country,
        "start_date": start_date,
        "end_date": end_date,
        "stale_hours": stale_hours,
        "rows": rows,
        "totals": {
            "sensor_count": len(rows),
            "ok_count": sum(1 for r in rows if r["status"] == "ok"),
            "attention_count": sum(1 for r in rows if r["status"] != "ok"),
            "upload_count": sum(r["upload_count"] for r in rows),
            "total_bytes": sum(r["total_bytes"] for r in rows),
            "telemetry_count": sum(r["telemetry_count"] for r in rows),
        },
        "daily_series": daily_series,
        "generated_at": timezone.now(),
    }
