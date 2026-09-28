from django.contrib import admin

from .models import MonitoringSession, RayhunterLogEntry


@admin.register(MonitoringSession)
class MonitoringSessionAdmin(admin.ModelAdmin):
    list_display = [
        "session_id",
        "sensor",
        "rayhunter_version",
        "has_gps",
        "created_at",
        "processed_at",
    ]
    list_filter = ["sensor", "has_gps", "rayhunter_version"]
    search_fields = ["session_id", "sensor__slug", "sensor__name"]
    readonly_fields = ["created_at", "processed_at"]


@admin.register(RayhunterLogEntry)
class RayhunterLogEntryAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "sensor",
        "qmdl_timestamp",
        "is_alert",
        "severity",
        "log_entry_preview",
        "latitude",
        "longitude",
    ]
    list_filter = ["is_alert", "severity", "sensor"]
    search_fields = ["log_entry", "sensor__slug"]
    readonly_fields = ["raw_payload"]

    @admin.display(description="Log entry")
    def log_entry_preview(self, obj):
        text = obj.log_entry or ""
        return text if len(text) <= 80 else text[:77] + "..."
