import bisect
import json


def load_gps_points(gps_path):
    """
    Reads a `<session>-gps.ndjson` file into a list of
    {"system_time": <unix seconds>, "lat": float, "lon": float} dicts,
    sorted by system_time. Returns [] if the path is None or the file
    doesn't exist — GPS is not guaranteed to be present for every session.
    """
    if not gps_path or not gps_path.is_file():
        return []

    points = []
    with gps_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("system_time") is None or d.get("lat") is None or d.get("lon") is None:
                continue
            points.append(d)

    points.sort(key=lambda p: p["system_time"])
    return points


def find_nearest_gps(points, target_unix_ts, max_gap_seconds=None):
    """
    Binary-search nearest-timestamp match against a GPS points list already
    sorted by system_time — mirrors the matching Rayhunter's own PCAP writer
    uses (find_nearest_gps in daemon/src/pcap.rs): nearest by absolute time
    difference, ties preferring the earlier reading.

    Returns the matching point dict, or None if `points` is empty, the
    target timestamp is None, or (when max_gap_seconds is set) the nearest
    match is further away than that.
    """
    if not points or target_unix_ts is None:
        return None

    times = [p["system_time"] for p in points]
    i = bisect.bisect_left(times, target_unix_ts)

    candidates = [c for c in (i - 1, i) if 0 <= c < len(points)]
    if not candidates:
        return None

    best = min(candidates, key=lambda c: (abs(points[c]["system_time"] - target_unix_ts), c))
    point = points[best]

    if max_gap_seconds is not None and abs(point["system_time"] - target_unix_ts) > max_gap_seconds:
        return None

    return point
