import logging
import os

from celery import shared_task

logger = logging.getLogger(__name__)

@shared_task(name="ingestion.tasks.scan_upload_directory")
def scan_upload_directory():
    """
    Periodically walks UPLOAD_ROOT and registers any new files in IngestedFile.
    New file = path not yet recorded for that sensor.
    """
    from django.conf import settings
    from sensors.models import Sensor
    from .models import IngestedFile

    upload_root = settings.UPLOAD_ROOT
    if not os.path.isdir(upload_root):
        return

    registered = 0

    for sensor in Sensor.objects.filter(is_active=True):
        sensor_dir = os.path.join(upload_root, sensor.slug)
        if not os.path.isdir(sensor_dir):
            continue

        for dirpath, _, filenames in os.walk(sensor_dir):
            for filename in filenames:

                full_path = os.path.join(dirpath, filename)
                relative_path = os.path.relpath(full_path, upload_root)

                file_size = None
                try:
                    file_size = os.path.getsize(full_path)
                except OSError:
                    pass

                _, created = IngestedFile.objects.get_or_create(
                    sensor=sensor,
                    relative_path=relative_path,
                    defaults={
                        "filename": filename,
                        "file_size": file_size,
                        "status": IngestedFile.STATUS_PENDING,
                    },
                )
                if created:
                    registered += 1
                    logger.info("Registered new file: %s", relative_path)

    if registered:
        logger.info("scan_upload_directory: registered %d new file(s)", registered)


@shared_task(name="ingestion.tasks.archive_ingested_files")
def archive_ingested_files(pks):
    """
    Background counterpart to IngestedFileAdmin.archive_action -- moves each
    eligible file from UPLOAD_ROOT into ARCHIVE_ROOT/uploads and stamps
    archived_at. Queued from the admin action rather than run inline: this
    can touch thousands of files of real disk I/O, and nginx's default
    60s proxy_read_timeout on the admin's own path (unlike /webdav/, which
    explicitly sets 3600s for uploads) 504s the browser well before a large
    batch finishes, even though gunicorn keeps running regardless --
    confirmed against a real production timeout. move_to_archive() commits
    archived_at per row as it goes, so progress is visible live via the
    dashboard's archive/pickup counts without needing to poll this task.

    The ArchiveBatchPending check that matters for the common case already
    happened synchronously in the admin action (see archive_action) so the
    user gets an immediate error instead of a silent background failure;
    this one only catches the rare race of two archive clicks in quick
    succession.
    """
    from django.conf import settings

    from .archiving import ArchiveBatchPending, move_to_archive
    from .models import IngestedFile

    queryset = IngestedFile.objects.filter(pk__in=pks)
    try:
        archived, missing = move_to_archive(
            queryset,
            source_root=settings.UPLOAD_ROOT,
            archive_subdir="uploads",
            path_field="relative_path",
            eligible_statuses=[IngestedFile.STATUS_DONE, IngestedFile.STATUS_ERROR],
        )
    except ArchiveBatchPending as exc:
        logger.warning("ingestion: archive batch refused -- %s", exc)
        return
    logger.info("ingestion: archived %d file(s), %d missing", archived, missing)


@shared_task(name="ingestion.tasks.reclaim_ingested_files")
def reclaim_ingested_files(pks):
    """Background counterpart to IngestedFileAdmin.reclaim_action -- see
    archive_ingested_files for why this runs as a task rather than inline."""
    from .archiving import reclaim_from_archive
    from .models import IngestedFile

    queryset = IngestedFile.objects.filter(pk__in=pks)
    deleted, missing, freed = reclaim_from_archive(
        queryset, archive_subdir="uploads", path_field="relative_path"
    )
    logger.info("ingestion: reclaimed %d file(s), freed %d bytes, %d missing", deleted, freed, missing)
