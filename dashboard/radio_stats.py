from django.db.models import Count, Sum

from radio.models import RadioCapture


def radio_stats_context():
    """
    Monitoring/reporting numbers for the radio pipeline -- deliberately
    computed from RadioCapture (one row per session, a few thousand rows)
    rather than RadioPacket (tens of millions of rows): RadioCapture.
    packet_count already holds each session's total, set once when the
    session is processed and left untouched by archiving/reclaiming, so
    these aggregates stay cheap and accurate regardless of how large
    RadioPacket grows or how much of it has since been archived off disk.
    """
    totals = RadioCapture.objects.aggregate(
        total_packets=Sum("packet_count"),
        capture_count=Count("id"),
    )

    by_country = list(
        RadioCapture.objects.values("session__sensor__country__name")
        .annotate(total_packets=Sum("packet_count"), capture_count=Count("id"))
        .order_by("-total_packets")
    )
    for row in by_country:
        row["country_name"] = row.pop("session__sensor__country__name") or "Unassigned"

    return {
        "radio_total_packets": totals["total_packets"] or 0,
        "radio_capture_count": totals["capture_count"] or 0,
        "radio_by_country": by_country,
    }
