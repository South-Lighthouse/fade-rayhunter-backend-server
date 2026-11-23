import os

from django.conf import settings
from django.contrib import admin, messages
from django.http import FileResponse, Http404
from django.urls import path, reverse
from django.utils.html import format_html

from ingestion.archiving import ArchiveStageFilter, any_batch_pending

from .models import RadioCapture, RadioPacket
from .tasks import archive_radio_captures, reclaim_radio_captures


@admin.register(RadioCapture)
class RadioCaptureAdmin(admin.ModelAdmin):
    list_display = [
        "download_link",
        "session",
        "status",
        "packet_count",
        "pcap_size",
        "created_at",
        "processed_at",
        "archived_at",
        "reclaimed_at",
    ]
    list_display_links = ["session"]
    list_filter = ["status", ArchiveStageFilter]
    search_fields = ["session__session_id", "session__sensor__slug"]
    readonly_fields = ["created_at", "processed_at", "archived_at", "reclaimed_at"]
    actions = ["archive_action", "reclaim_action"]

    @admin.display(description="")
    def download_link(self, obj):
        if not obj.pcap_path:
            return ""
        url = reverse("admin:radio_radiocapture_download", args=[obj.pk])
        return format_html('<a href="{}" title="Download">⬇</a>', url)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/download/",
                self.admin_site.admin_view(self.download_view),
                name="radio_radiocapture_download",
            ),
        ]
        return custom + urls

    def download_view(self, request, pk):
        obj = RadioCapture.objects.filter(pk=pk).first()
        if obj is None or not obj.pcap_path:
            raise Http404
        # archived (not yet reclaimed) PCAPs have been moved out of
        # RADIO_PCAP_ROOT into ARCHIVE_ROOT -- see ingestion/archiving.py
        # (shared by this app and `ingestion`).
        if obj.archived_at and not obj.reclaimed_at:
            root = os.path.join(settings.ARCHIVE_ROOT, "radio_pcaps")
        else:
            root = settings.RADIO_PCAP_ROOT
        full_path = os.path.join(root, obj.pcap_path)
        if not os.path.isfile(full_path):
            raise Http404
        return FileResponse(
            open(full_path, "rb"), as_attachment=True, filename=os.path.basename(obj.pcap_path)
        )

    @admin.action(description="Archive selected captures (move PCAP to archive dir)")
    def archive_action(self, request, queryset):
        # See ingestion.admin.IngestedFileAdmin.archive_action for why this
        # queues a background task instead of moving files inline, and why
        # the pending-batch check stays synchronous here.
        if any_batch_pending():
            self.message_user(
                request,
                "A previous archive batch hasn't been reclaimed yet -- pull everything from "
                "the archive dir and run the reclaim action first.",
                messages.ERROR,
            )
            return
        pks = list(queryset.values_list("pk", flat=True))
        archive_radio_captures.delay(pks)
        self.message_user(
            request,
            f"Archiving {len(pks)} capture(s) in the background -- watch the dashboard's "
            "archive status card for progress.",
            messages.SUCCESS,
        )

    @admin.action(description="Reclaim space for archived captures (delete from archive dir)")
    def reclaim_action(self, request, queryset):
        pks = list(queryset.values_list("pk", flat=True))
        reclaim_radio_captures.delay(pks)
        self.message_user(
            request,
            f"Reclaiming {len(pks)} capture(s) in the background -- watch the dashboard's "
            "archive status card for progress.",
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
