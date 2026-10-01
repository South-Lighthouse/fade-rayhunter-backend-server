from django.conf import settings
from django.contrib import admin, messages
from django.template.defaultfilters import filesizeformat

from ingestion.archiving import ArchiveBatchPending, move_to_archive, reclaim_from_archive

from .models import RadioCapture, RadioPacket


@admin.register(RadioCapture)
class RadioCaptureAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "status",
        "packet_count",
        "pcap_size",
        "created_at",
        "processed_at",
        "archived_at",
        "reclaimed_at",
    ]
    list_filter = ["status"]
    search_fields = ["session__session_id", "session__sensor__slug"]
    readonly_fields = ["created_at", "processed_at", "archived_at", "reclaimed_at"]
    actions = ["archive_action", "reclaim_action"]

    @admin.action(description="Archive selected captures (move PCAP to archive dir)")
    def archive_action(self, request, queryset):
        try:
            archived, missing = move_to_archive(
                queryset,
                source_root=settings.RADIO_PCAP_ROOT,
                archive_subdir="radio_pcaps",
                path_field="pcap_path",
                eligible_statuses=[RadioCapture.STATUS_DONE],
            )
        except ArchiveBatchPending as exc:
            self.message_user(request, str(exc), messages.ERROR)
            return
        msg = f"Archived {archived} capture(s)."
        if missing:
            msg += f" {missing} had no PCAP file on disk (DB-only, marked archived anyway)."
        self.message_user(request, msg, messages.SUCCESS)

    @admin.action(description="Reclaim space for archived captures (delete from archive dir)")
    def reclaim_action(self, request, queryset):
        deleted, missing, freed = reclaim_from_archive(
            queryset, archive_subdir="radio_pcaps", path_field="pcap_path"
        )
        self.message_user(
            request,
            f"Deleted {deleted} file(s), freed {filesizeformat(freed)}. {missing} were already missing.",
            messages.SUCCESS,
        )


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
