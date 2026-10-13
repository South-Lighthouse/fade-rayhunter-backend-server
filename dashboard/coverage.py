def coverage_points_for(sensor_ids, start_date, end_date):
    """
    Distinct [lat, lon] pairs with a radio reading in [start_date, end_date]
    (inclusive) across the given sensors. Reads only radio.CoveragePoint --
    a precomputed, deduplicated-to-~111m-grid table -- never RadioPacket
    (tens of millions of rows), so this stays cheap regardless of how wide
    the date range is or how much raw packet data exists.
    """
    from radio.models import CoveragePoint

    rows = (
        CoveragePoint.objects.filter(sensor_id__in=sensor_ids, date__range=(start_date, end_date))
        .values_list("latitude", "longitude")
        .distinct()
    )
    return [[float(lat), float(lon)] for lat, lon in rows]
