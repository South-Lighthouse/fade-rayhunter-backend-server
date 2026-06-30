from django.contrib import admin
from .models import Sensor


@admin.register(Sensor)
class SensorAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "webdav_user", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "slug", "webdav_user"]
    readonly_fields = ["slug", "api_key", "created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["name", "slug", "is_active", "notes"]}),
        ("WebDAV credentials", {"fields": ["webdav_user", "webdav_password"]}),
        ("Telemetry API key", {"fields": ["api_key"],
                               "description": "Send this key in the Android app as: Authorization: Bearer <key>"}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]
