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
    # RadioPacket is a tens-of-millions-of-rows table. The admin changelist's
    # two defaults that are fine on small tables are ruinous here:
    #  - show_full_result_count runs an unfiltered COUNT(*) on every page
    #    load; InnoDB has no fast row-count shortcut, so that's a full scan.
    #  - the model's own Meta.ordering ("capture", "qmdl_timestamp") has no
    #    matching composite index, so MySQL filesorts the whole table just
    #    to paginate page 1. Ordering by -id instead is free (primary key,
    #    always indexed, no filesort) -- overridden only here, not on the
    #    model, since small per-capture querysets elsewhere legitimately
    #    want the chronological order.
    # This keeps the page usable for *targeted* lookups (search, filter by
    # sensor/packet_type); it's not meant for browsing the whole table --
    # see ingestion.archiving/dashboard for the read-only DB / aggregate
    # reporting paths meant for that.
    #
    # list_select_related = [] (an empty list, NOT False) is the one that
    # actually matters: with it left at the default False, Django's
    # ModelAdmin sees "capture" and "sensor" (both FKs) in list_display and
    # auto-applies a bare .select_related() -- which follows every reachable
    # FK chain it can find (capture -> session -> sensor, AND a second,
    # separate join straight to sensor), turning the row query into a
    # 4-table join across a ~170-column table. That's what was actually
    # taking 100+ seconds, not the ordering or the count. The per-row N+1
    # lookups this falls back to instead (for rendering capture/sensor as
    # text) are proven fast -- 0.1s for 100 rows -- so there's no need to
    # replace it with an explicit select_related list.
    show_full_result_count = False
    ordering = ["-id"]
    list_select_related = []
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
