import os

from django.conf import settings
from django.contrib import admin, messages
from django.http import FileResponse, Http404
from django.template.defaultfilters import filesizeformat
from django.urls import path, reverse
from django.utils.html import format_html

from .archiving import ArchiveBatchPending, move_to_archive, reclaim_from_archive
from .models import IngestedFile

ELIGIBLE_ARCHIVE_STATUSES = [IngestedFile.STATUS_DONE, IngestedFile.STATUS_ERROR]


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
    list_filter = ["status", "sensor"]
    search_fields = ["filename", "relative_path"]
    readonly_fields = ["uploaded_at", "processed_at", "archived_at", "reclaimed_at"]
    actions = ["archive_action", "reclaim_action"]

    @admin.action(description="Archive selected files (move to archive dir)")
    def archive_action(self, request, queryset):
        try:
            archived, missing = move_to_archive(
                queryset,
                source_root=settings.UPLOAD_ROOT,
                archive_subdir="uploads",
                path_field="relative_path",
                eligible_statuses=ELIGIBLE_ARCHIVE_STATUSES,
            )
        except ArchiveBatchPending as exc:
            self.message_user(request, str(exc), messages.ERROR)
            return
        msg = f"Archived {archived} file(s)."
        if missing:
            msg += f" {missing} had no file on disk (DB-only, marked archived anyway)."
        self.message_user(request, msg, messages.SUCCESS)

    @admin.action(description="Reclaim space for archived files")
    def reclaim_action(self, request, queryset):
        deleted, missing, freed = reclaim_from_archive(
            queryset, archive_subdir="uploads", path_field="relative_path"
        )
        self.message_user(
            request,
            f"Deleted {deleted} file(s), freed {filesizeformat(freed)}. {missing} were already missing.",
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
