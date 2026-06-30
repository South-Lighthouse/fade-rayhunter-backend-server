import base64
import io
import json

import qrcode
from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html

from .models import Sensor


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "webdav_user", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug", "webdav_user"]
    readonly_fields = ["slug", "api_key", "telemetry_qr_code", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "slug", "is_active", "notes"]}),
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
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]

    @admin.display(description="QR code")
    def telemetry_qr_code(self, obj):
        if not obj.api_key:
            return "—"

        base_url = getattr(settings, "TELEMETRY_BASE_URL", "http://localhost:8000").rstrip("/")
        payload = json.dumps({
            "telemetry_url": f"{base_url}/api/telemetry/",
            "api_key": obj.api_key,
        })

        img = qrcode.make(payload)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode()

        return format_html(
            '<img src="data:image/png;base64,{}" alt="QR code" '
            'style="width:200px;height:200px;image-rendering:pixelated;" '
            'title="Right-click → Copy image to share">',
            encoded,
        )
