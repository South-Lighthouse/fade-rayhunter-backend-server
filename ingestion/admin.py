import os

from django.conf import settings
from django.contrib import admin, messages
from django.http import FileResponse, Http404
from django.urls import path, reverse
from django.utils.html import format_html

from .archiving import ArchiveStageFilter, any_batch_pending
from .models import IngestedFile
from .tasks import archive_ingested_files, reclaim_ingested_files


@admin.register(IngestedFile)
class IngestedFileAdmin(admin.ModelAdmin):
    list_display = [
        "download_link",
        "filename",
        "sensor",
        "status",
        "file_size",
        "uploaded_at",
        "archived_at",
        "reclaimed_at",
    ]
    list_display_links = ["filename"]
    list_filter = ["status", "sensor", ArchiveStageFilter]
    search_fields = ["filename", "relative_path"]
    readonly_fields = ["uploaded_at", "processed_at", "archived_at", "reclaimed_at"]
    actions = ["archive_action", "reclaim_action"]

    @admin.action(description="Archive selected files (move to archive dir)")
    def archive_action(self, request, queryset):
        # The actual move runs in the background (see ingestion.tasks) --
        # large batches were 504ing the admin request (nginx's default
        # location has no extended timeout, unlike /webdav/). The pending-
        # batch check stays synchronous here, cheap, so the common case
        # still gets an immediate error instead of a silent queued failure.
        if any_batch_pending():
            self.message_user(
                request,
                "A previous archive batch hasn't been reclaimed yet -- pull everything from "
                "the archive dir and run the reclaim action first.",
                messages.ERROR,
            )
            return
        pks = list(queryset.values_list("pk", flat=True))
        archive_ingested_files.delay(pks)
        self.message_user(
            request,
            f"Archiving {len(pks)} file(s) in the background -- watch the dashboard's "
            "archive status card for progress.",
            messages.SUCCESS,
        )

    @admin.action(description="Reclaim space for archived files")
    def reclaim_action(self, request, queryset):
        pks = list(queryset.values_list("pk", flat=True))
        reclaim_ingested_files.delay(pks)
        self.message_user(
            request,
            f"Reclaiming {len(pks)} file(s) in the background -- watch the dashboard's "
            "archive status card for progress.",
            messages.SUCCESS,
        )

    @admin.display(description="")
    def download_link(self, obj):
        url = reverse("admin:ingestion_ingestedfile_download", args=[obj.pk])
        return format_html('<a href="{}" title="Download">⬇</a>', url)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/download/",
                self.admin_site.admin_view(self.download_view),
                name="ingestion_ingestedfile_download",
            ),
        ]
        return custom + urls

    def download_view(self, request, pk):
        obj = IngestedFile.objects.filter(pk=pk).first()
        if obj is None:
            raise Http404
        # archived (not yet reclaimed) files have been moved out of
        # UPLOAD_ROOT into ARCHIVE_ROOT -- see ingestion/archiving.py.
        if obj.archived_at and not obj.reclaimed_at:
            root = os.path.join(settings.ARCHIVE_ROOT, "uploads")
        else:
            root = settings.UPLOAD_ROOT
        full_path = os.path.join(root, obj.relative_path)
        if not os.path.isfile(full_path):
            raise Http404
        return FileResponse(open(full_path, "rb"), as_attachment=True, filename=obj.filename)
