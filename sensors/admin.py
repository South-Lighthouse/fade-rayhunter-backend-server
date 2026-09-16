import base64
import io
import json
from datetime import date, timedelta

import qrcode
from django.conf import settings
from django.contrib import admin
from django.db.models import Count
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html

from dashboard.pulse import annotate_pulse, daily_series_for_range, dashboard_groups, sensor_timeline_events
from dashboard.reports import build_country_report
from dashboard.svg_charts import render_daily_series_svg

from .models import Country, Sensor, SensorType


def _stale_hours_from_request(request):
    default = getattr(settings, "SENSOR_STALE_HOURS", 96)
    try:
        return int(request.GET.get("stale_hours") or default)
    except (TypeError, ValueError):
        return default


def _date_range_from_request(request, default_days):
    """
    Parses ?start=&end= (YYYY-MM-DD) from the request, falling back to a
    trailing `default_days`-day window ending today. Swaps the two if the
    user enters them backwards, rather than erroring.
    """
    today = date.today()

    def _parse(value, fallback):
        if not value:
            return fallback
        try:
            return date.fromisoformat(value)
        except ValueError:
            return fallback

    start_date = _parse(request.GET.get("start"), today - timedelta(days=default_days - 1))
    end_date = _parse(request.GET.get("end"), today)
    if end_date < start_date:
        start_date, end_date = end_date, start_date
    return start_date, end_date


@admin.register(SensorType)
class SensorTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "default_ip_address"]
    search_fields = ["name"]


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "sensor_count", "report_button"]
    search_fields = ["name", "code"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_sensor_count=Count("sensors"))

    @admin.display(description="Sensors", ordering="_sensor_count")
    def sensor_count(self, obj):
        return obj._sensor_count

    @admin.display(description="Report")
    def report_button(self, obj):
        url = reverse("admin:sensors_country_report", args=[obj.pk])
        return format_html('<a class="button" href="{}">Generate report ↗</a>', url)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/report/",
                self.admin_site.admin_view(self.report_view),
                name="sensors_country_report",
            ),
        ]
        return custom + urls

    def report_view(self, request, pk):
        country = get_object_or_404(Country, pk=pk)

        start_date, end_date = _date_range_from_request(request, default_days=7)
        stale_hours = _stale_hours_from_request(request)

        context = build_country_report(country, start_date, end_date, stale_hours)
        context["chart_svg"] = render_daily_series_svg(
            context["daily_series"], label=f"Uploads per day — {country.name}"
        )
        context.update(self.admin_site.each_context(request))
        context["title"] = f"{country.name} report"

        return render(request, "dashboard/country_report.html", context)


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = [
        "info_sheet_button",
        "name",
        "slug",
        "sensor_type",
        "country",
        "webdav_user",
        "is_active",
        "created_at",
    ]
    list_display_links = ["name"]
    list_editable = ["country"]
    list_filter = ["is_active", "sensor_type", "country"]
    search_fields = ["name", "slug", "webdav_user"]
    readonly_fields = ["slug", "api_key", "telemetry_qr_code", "info_sheet_button", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "slug", "is_active", "notes"]}),
        ("Device", {"fields": ["sensor_type", "country"]}),
        ("WebDAV credentials", {"fields": ["webdav_user", "webdav_password"]}),
        (
            "Telemetry API key",
            {
                "fields": ["api_key", "telemetry_qr_code"],
                "description": (
                    "Send this key in the Android app as: Authorization: Bearer &lt;key&gt;. "
                    "Scan the QR code to configure the app automatically."
                ),
            },
        ),
        ("Info sheet", {"fields": ["info_sheet_button"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]

    @staticmethod
    def _build_qr_b64(sensor):
        base_url = getattr(settings, "TELEMETRY_BASE_URL", "http://localhost:8000").rstrip("/")
        data = {
            "telemetry_url": f"{base_url}/api/telemetry/",
            "api_key": (sensor.api_key or "").strip(),
            "webdav_url": f"{base_url}/webdav/{sensor.slug}/",
            "webdav_user": (sensor.webdav_user or "").strip(),
            "webdav_password": (sensor.webdav_password or "").strip(),
        }
        if sensor.sensor_type and sensor.sensor_type.default_ip_address.strip():
            data["device_ip"] = sensor.sensor_type.default_ip_address.strip()
        payload = json.dumps(data)
        img = qrcode.make(payload)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    @admin.display(description="QR code")
    def telemetry_qr_code(self, obj):
        if not obj.api_key:
            return "—"
        encoded = self._build_qr_b64(obj)
        return format_html(
            '<img src="data:image/png;base64,{}" alt="QR code" '
            'style="width:200px;height:200px;image-rendering:pixelated;" '
            'title="Right-click → Copy image to share">',
            encoded,
        )

    @admin.display(description="Info sheet")
    def info_sheet_button(self, obj):
        if not obj.pk:
            return "—"
        url = reverse("admin:sensors_sensor_info", args=[obj.pk])
        return format_html('<a href="{}" target="_blank" class="button">Open info sheet ↗</a>', url)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "dashboard/",
                self.admin_site.admin_view(self.dashboard_view),
                name="sensors_sensor_dashboard",
            ),
            path(
                "<int:pk>/info/",
                self.admin_site.admin_view(self.info_view),
                name="sensors_sensor_info",
            ),
            path(
                "<int:pk>/pulse/",
                self.admin_site.admin_view(self.pulse_view),
                name="sensors_sensor_pulse",
            ),
        ]
        return custom + urls

    def info_view(self, request, pk):
        sensor = get_object_or_404(Sensor, pk=pk)
        qr_b64 = self._build_qr_b64(sensor) if sensor.api_key else None
        base_url = getattr(settings, "TELEMETRY_BASE_URL", "http://localhost:8000").rstrip("/")
        context = {
            **self.admin_site.each_context(request),
            "sensor": sensor,
            "qr_b64": qr_b64,
            "webdav_url": f"{base_url}/webdav/{sensor.slug}/",
            "title": f"Info sheet — {sensor.name}",
        }
        return render(request, "sensors/sensor_info.html", context)

    def dashboard_view(self, request):
        stale_hours = _stale_hours_from_request(request)
        groups = dashboard_groups(stale_hours)
        for group in groups:
            country_name = group["country"].name if group["country"] else "Unassigned"
            group["trend_svg"] = render_daily_series_svg(
                group["trend_series"], label=f"Uploads per day — {country_name}"
            )

        context = {
            **self.admin_site.each_context(request),
            "title": "Sensor dashboard",
            "groups": groups,
            "stale_hours": stale_hours,
        }
        return render(request, "dashboard/sensor_dashboard.html", context)

    def pulse_view(self, request, pk):
        sensor = get_object_or_404(Sensor, pk=pk)
        stale_hours = _stale_hours_from_request(request)
        start_date, end_date = _date_range_from_request(request, default_days=30)

        pulsed_sensor = annotate_pulse(Sensor.objects.filter(pk=sensor.pk), stale_hours)[0]
        upload_series, _ = daily_series_for_range([sensor.pk], start_date, end_date)
        events = sensor_timeline_events(sensor, start_date, end_date)

        context = {
            **self.admin_site.each_context(request),
            "title": f"{sensor.name} pulse",
            "sensor": pulsed_sensor,
            "stale_hours": stale_hours,
            "start_date": start_date,
            "end_date": end_date,
            "chart_svg": render_daily_series_svg(upload_series, label=f"Uploads per day — {sensor.name}"),
            "events": events,
        }
        return render(request, "dashboard/sensor_pulse.html", context)
