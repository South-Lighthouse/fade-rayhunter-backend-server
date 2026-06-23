from django.contrib import admin
from .models import IngestedFile


@admin.register(IngestedFile)
class IngestedFileAdmin(admin.ModelAdmin):
    list_display = ["filename", "sensor", "status", "file_size", "uploaded_at"]
    list_filter = ["status", "sensor"]
    search_fields = ["filename", "relative_path"]
    readonly_fields = ["uploaded_at", "processed_at"]
