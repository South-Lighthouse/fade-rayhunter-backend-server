from django.contrib import admin
from .models import TelemetryRecord


@admin.register(TelemetryRecord)
class TelemetryRecordAdmin(admin.ModelAdmin):
    list_display = ["sensor", "event_type", "message", "device_timestamp", "received_at"]
    list_filter = ["sensor", "event_type"]
    search_fields = ["sensor__slug", "event_type", "message"]
    readonly_fields = ["received_at", "raw_payload"]
