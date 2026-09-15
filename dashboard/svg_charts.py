import html


def render_daily_series_svg(series, *, width=640, height=140, color="#3b82f6", label=""):
    """
    Renders a simple line chart as an inline <svg> string for a daily count
    series: an iterable of (date, count) tuples, already sorted ascending.

    No JS dependency — each point carries a <title> for a native browser
    tooltip. The caller is responsible for marking the result safe (it only
    ever interpolates escaped text and formatted numbers).
    """
    points = list(series)
    if not points:
        return '<p class="chart-empty">No data in this range.</p>'

    padding = 24
    plot_w = width - 2 * padding
    plot_h = height - 2 * padding

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

    circles = []
    for (day, count), (x, y) in zip(points, coords):
        title = html.escape(f"{day}: {count}")
        circles.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"><title>{title}</title></circle>')

    baseline_y = y_for(0)

    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
        f'role="img" aria-label="{html.escape(label)}">'
        f'<line x1="{padding}" y1="{baseline_y:.1f}" x2="{width - padding}" y2="{baseline_y:.1f}" '
        f'stroke="#ccc" stroke-width="1"/>'
        f'<polyline points="{polyline_points}" fill="none" stroke="{color}" stroke-width="2"/>'
        f'{"".join(circles)}'
        f'<text x="{padding}" y="{height - 4}" font-size="10" fill="#888">{html.escape(str(points[0][0]))}</text>'
        f'<text x="{width - padding}" y="{height - 4}" font-size="10" fill="#888" '
        f'text-anchor="end">{html.escape(str(points[-1][0]))}</text>'
        f"</svg>"
    )
