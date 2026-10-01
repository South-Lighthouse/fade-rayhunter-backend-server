import shutil

from django.conf import settings
from django.db.models import Sum

from ingestion.models import IngestedFile
from radio.models import RadioCapture


def _usage(path):
    try:
        total, used, free = shutil.disk_usage(path)
    except OSError:
        return None
    return {"path": path, "total": total, "used": used, "free": free}


def archive_context():
    """
    Visibility for the admin's archive/pickup/reclaim decision: free space
    on each relevant root, how much is ready to archive (processed, not
    yet moved to ARCHIVE_ROOT), and how much is currently sitting in
    ARCHIVE_ROOT waiting for the admin to pull it off the server.
    """
    ingested_ready = IngestedFile.objects.filter(
        status__in=[IngestedFile.STATUS_DONE, IngestedFile.STATUS_ERROR], archived_at__isnull=True
    )
    ingested_waiting = IngestedFile.objects.filter(archived_at__isnull=False, reclaimed_at__isnull=True)
    radio_ready = RadioCapture.objects.filter(status=RadioCapture.STATUS_DONE, archived_at__isnull=True)
    radio_waiting = RadioCapture.objects.filter(archived_at__isnull=False, reclaimed_at__isnull=True)

    return {
        "archive_disk": _usage(settings.ARCHIVE_ROOT),
        "uploads_disk": _usage(settings.UPLOAD_ROOT),
        "pcap_disk": _usage(settings.RADIO_PCAP_ROOT),
        "ingested_ready_count": ingested_ready.count(),
        "ingested_ready_bytes": ingested_ready.aggregate(total=Sum("file_size"))["total"] or 0,
        "ingested_waiting_count": ingested_waiting.count(),
        "ingested_waiting_bytes": ingested_waiting.aggregate(total=Sum("file_size"))["total"] or 0,
        "radio_ready_count": radio_ready.count(),
        "radio_ready_bytes": radio_ready.aggregate(total=Sum("pcap_size"))["total"] or 0,
        "radio_waiting_count": radio_waiting.count(),
        "radio_waiting_bytes": radio_waiting.aggregate(total=Sum("pcap_size"))["total"] or 0,
    }
