from django.contrib import admin

from .models import RadioCapture, RadioPacket


@admin.register(RadioCapture)
class RadioCaptureAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "status",
        "packet_count",
        "created_at",
        "processed_at",
    ]
    list_filter = ["status"]
    search_fields = ["session__session_id", "session__sensor__slug"]
    readonly_fields = ["created_at", "processed_at"]


@admin.register(RadioPacket)
class RadioPacketAdmin(admin.ModelAdmin):
    list_display = [
        "capture",
        "sensor",
        "qmdl_timestamp",
        "packet_type",
        "timing_advance",
        "latitude",
        "longitude",
    ]
    list_filter = ["packet_type", "sensor"]
    search_fields = ["sensor__slug", "capture__session__session_id"]
    readonly_fields = ["raw_fields"]
