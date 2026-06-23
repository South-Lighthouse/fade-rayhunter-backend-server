from django.contrib import admin
from .models import TelemetryRecord


@admin.register(TelemetryRecord)
class TelemetryRecordAdmin(admin.ModelAdmin):
    list_display = ["device_id", "sensor", "ip_address", "received_at"]
    list_filter = ["sensor"]
    search_fields = ["device_id", "ip_address"]
    readonly_fields = ["received_at"]
