from datetime import datetime, time

from django.utils import timezone
from django.utils.html import escape


def alerts_for(sensor_ids, start_date, end_date):
    """
    Alert-flagged RayhunterLogEntry rows for the given sensors in the
    inclusive [start_date, end_date] range, most recent first.

    is_alert=True is rare (an analyzer actually firing, not just a logged
    line) -- RayhunterLogEntry as a whole is a high-volume table, but the
    alert subset stays small regardless of how much log data exists, so
    this is cheap even as the underlying table grows. Uses the existing
    (sensor, is_alert) index.
    """
    from captures.models import RayhunterLogEntry

    range_start = timezone.make_aware(datetime.combine(start_date, time.min))
    range_end = timezone.make_aware(datetime.combine(end_date, time.max))

    return list(
        RayhunterLogEntry.objects.filter(
            sensor_id__in=sensor_ids,
            is_alert=True,
            qmdl_timestamp__range=(range_start, range_end),
        )
        .select_related("sensor")
        .order_by("-qmdl_timestamp")
    )


def alert_points_for(alerts):
    """
    [lat, lon, popup_html] triples for alerts with a GPS fix, for the map.
    Takes the already-fetched list from alerts_for() rather than querying
    again -- callers that need both the table rows and the map points (both
    report views do) only hit the DB once.

    Unlike coverage_points_for(), these are never deduplicated: each alert
    is a specific, individually-worth-seeing event, and the set is small by
    construction (see alerts_for()).

    The popup is rendered as raw HTML by Leaflet (bindPopup inserts it as
    innerHTML), so every field is escaped before interpolation even though
    log_entry is normally a fixed analyzer-template string, not freeform
    device input -- cheap insurance against a malformed/unexpected message.
    """
    points = []
    for alert in alerts:
        if alert.latitude is None or alert.longitude is None:
            continue
        when = alert.qmdl_timestamp.strftime("%Y-%m-%d %H:%M") if alert.qmdl_timestamp else "unknown time"
        popup = (
            f"{escape(when)} &middot; {escape(alert.sensor.slug)} &middot; {escape(alert.severity)}"
            f"<br>{escape(alert.log_entry)}"
        )
        points.append([alert.latitude, alert.longitude, popup])
    return points
