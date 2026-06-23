import logging
import os

from celery import shared_task

logger = logging.getLogger(__name__)

TRACKED_EXTENSIONS = {".qmdl", ".json"}


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
                _, ext = os.path.splitext(filename)
                if ext.lower() not in TRACKED_EXTENSIONS:
                    continue

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
