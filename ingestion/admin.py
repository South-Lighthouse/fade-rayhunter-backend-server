import os

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import path, reverse
from django.utils.html import format_html

from .models import IngestedFile


@admin.register(IngestedFile)
class IngestedFileAdmin(admin.ModelAdmin):
    list_display = ["download_link", "filename", "sensor", "status", "file_size", "uploaded_at"]
    list_display_links = ["filename"]
    list_filter = ["status", "sensor"]
    search_fields = ["filename", "relative_path"]
    readonly_fields = ["uploaded_at", "processed_at"]

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
        full_path = os.path.join(settings.UPLOAD_ROOT, obj.relative_path)
        if not os.path.isfile(full_path):
            raise Http404
        return FileResponse(open(full_path, "rb"), as_attachment=True, filename=obj.filename)
