import base64
import io
import json

import qrcode
from django.conf import settings
from django.contrib import admin
from django.shortcuts import get_object_or_404, render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Sensor, SensorType


@admin.register(SensorType)
class SensorTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "default_ip_address"]
    search_fields = ["name"]


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ["info_sheet_button", "name", "slug", "sensor_type", "webdav_user", "is_active", "created_at"]
    list_display_links = ["name"]
    list_filter = ["is_active", "sensor_type"]
    search_fields = ["name", "slug", "webdav_user"]
    readonly_fields = ["slug", "api_key", "telemetry_qr_code", "info_sheet_button", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "slug", "is_active", "notes"]}),
        ("Device", {"fields": ["sensor_type"]}),
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
                "<int:pk>/info/",
                self.admin_site.admin_view(self.info_view),
                name="sensors_sensor_info",
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
