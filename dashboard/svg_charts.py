import html


def render_daily_series_svg(series, *, width=640, height=140, color="#3b82f6", label=""):
    """
    Renders a simple line chart as an inline <svg> string for a daily count
    series: an iterable of (date, count) tuples, already sorted ascending.

    No JS dependency. Each point gets an oversized invisible hit-circle plus
    a CSS-only (`:hover`) tooltip and vertical guide line — much easier to
    land on and read than the native SVG <title> tooltip alone, especially
    with many closely-spaced days. The caller is responsible for marking the
    result safe (it only ever interpolates escaped text and formatted
    numbers). Requires the `.chart-point` hover rules in _report_style.html.
    """
    points = list(series)
    if not points:
        return '<p class="chart-empty">No data in this range.</p>'

    padding = 24
    plot_w = width - 2 * padding
    plot_h = height - 2 * padding
    plot_bottom = padding + plot_h

    values = [count for _, count in points]
    max_value = max(values) or 1
    n = len(points)

    def x_for(i):
        if n == 1:
            return padding + plot_w / 2
        return padding + (plot_w * i / (n - 1))

    def y_for(value):
        return padding + plot_h * (1 - value / max_value)

    coords = [(x_for(i), y_for(count)) for i, (_, count) in enumerate(points)]
    polyline_points = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    baseline_y = y_for(0)

    point_groups = []
    for (day, count), (x, y) in zip(points, coords):
        short_label = html.escape(f"{day:%b %d}: {count}")
        point_groups.append(
            f'<g class="chart-point">'
            f'<line class="hover-guide" x1="{x:.1f}" y1="{padding}" x2="{x:.1f}" y2="{plot_bottom:.1f}"/>'
            f'<circle class="hit-area" cx="{x:.1f}" cy="{y:.1f}" r="7" fill="transparent"/>'
            f'<circle class="point-dot" cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>'
            f'<g class="tooltip" transform="translate({x:.1f},12)">'
            f'<rect x="-30" y="-10" width="60" height="16" rx="3"/>'
            f'<text x="0" y="2" text-anchor="middle">{short_label}</text>'
            f"</g>"
            f"</g>"
        )

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="{html.escape(label)}">'
        f'<line x1="{padding}" y1="{baseline_y:.1f}" x2="{width - padding}" y2="{baseline_y:.1f}" '
        f'stroke="#ccc" stroke-width="1"/>'
        f'<polyline points="{polyline_points}" fill="none" stroke="{color}" stroke-width="2"/>'
        f'{"".join(point_groups)}'
        f'<text x="{padding}" y="{height - 4}" font-size="10" fill="#888">{html.escape(f"{points[0][0]:%b %d}")}</text>'
        f'<text x="{width - padding}" y="{height - 4}" font-size="10" fill="#888" '
        f'text-anchor="end">{html.escape(f"{points[-1][0]:%b %d}")}</text>'
        f"</svg>"
    )
