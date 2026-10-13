import math
from datetime import datetime, time

from django.utils import timezone
from django.utils.html import escape

# Fixed zoom for the per-alert thumbnail map: street/neighborhood-level
# context, a reasonable "at a glance, where was this" view everywhere from
# a dense city to open countryside. Not configurable per-report -- one
# sensible default keeps every thumbnail directly comparable.
THUMBNAIL_ZOOM = 15
THUMBNAIL_TILE_SIZE = 256


def alerts_for(sensor_ids, start_date, end_date):
    """
    Alert-flagged RayhunterLogEntry rows for the given sensors in the
    inclusive [start_date, end_date] range, most recent first. Each row
    with a GPS fix gets two extra attributes for report templates:
    `maps_url` (opens the exact coordinate in Google Maps) and `thumb`
    (a static mini-map -- see _tile_for_point()). Rows without a fix get
    both set to None.

    is_alert=True is rare (an analyzer actually firing, not just a logged
    line) -- RayhunterLogEntry as a whole is a high-volume table, but the
    alert subset stays small regardless of how much log data exists, so
    this is cheap even as the underlying table grows. Uses the existing
    (sensor, is_alert) index.
    """
    from captures.models import RayhunterLogEntry

    range_start = timezone.make_aware(datetime.combine(start_date, time.min))
    range_end = timezone.make_aware(datetime.combine(end_date, time.max))

    alerts = list(
        RayhunterLogEntry.objects.filter(
            sensor_id__in=sensor_ids,
            is_alert=True,
            qmdl_timestamp__range=(range_start, range_end),
        )
        .select_related("sensor")
        .order_by("-qmdl_timestamp")
    )

    for alert in alerts:
        if alert.latitude is not None and alert.longitude is not None:
            alert.maps_url = f"https://www.google.com/maps?q={alert.latitude},{alert.longitude}"
            alert.thumb = _tile_for_point(alert.latitude, alert.longitude)
        else:
            alert.maps_url = None
            alert.thumb = None

    return alerts


def _tile_for_point(lat, lon, zoom=THUMBNAIL_ZOOM):
    """
    Standard Web Mercator slippy-map tile math: which single map tile (at
    `zoom`) contains (lat, lon), plus the point's position within that
    tile as a percentage (so the template can place a marker with plain
    CSS `left/top: X%`, independent of however large the thumbnail is
    displayed).

    Deliberately one raw tile per alert rather than a true centered static
    map (which would need stitching several tiles together): this keeps
    each thumbnail a single small cached image -- reliable under
    browser-print-to-PDF (a plain <img>, no async JS map to race against
    window.print()) and genuinely cheap at scale (alerts near each other
    land on the very same tile URL, so the browser/PDF renderer fetches it
    once and reuses it). The tradeoff is the alert isn't always dead-center
    in its thumbnail -- acceptable for an at-a-glance "where was this"
    view; real centering can be added later (e.g. a 2x2 tile stitch) if
    that tradeoff turns out to matter.
    """
    lat_rad = math.radians(lat)
    n = 2.0**zoom
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.log(math.tan(lat_rad) + 1 / math.cos(lat_rad)) / math.pi) / 2.0 * n
    tile_x, tile_y = int(x), int(y)
    return {
        "tile_url": (
            "https://server.arcgisonline.com/ArcGIS/rest/services/"
            f"World_Street_Map/MapServer/tile/{zoom}/{tile_y}/{tile_x}"
        ),
        "marker_left_pct": round((x - tile_x) * 100, 2),
        "marker_top_pct": round((y - tile_y) * 100, 2),
    }


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
