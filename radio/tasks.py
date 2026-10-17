import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name="radio.tasks.process_pending_radio_captures")
def process_pending_radio_captures():
    """
    Periodically converts QMDL+GPS into PCAPs and RadioPacket rows for every
    active sensor's pending sessions -- the same logic the
    process_radio_captures management command wraps.

    Bounded per sensor per run via RADIO_PROCESSING_BATCH_SIZE, mirroring
    captures.tasks.process_pending_monitoring_sessions -- iterating per
    sensor (not a single global limit) means one sensor with a large
    backlog (e.g. after a connectivity outage) can't starve every other
    sensor's newer sessions out of a given run.
    """
    from sensors.models import Sensor

    from .models import RadioCapture
    from .parsing import discover_pending_captures, process_capture

    batch_size = getattr(settings, "RADIO_PROCESSING_BATCH_SIZE", 20)
    processed = 0
    errors = 0

    for sensor in Sensor.objects.filter(is_active=True):
        for session in discover_pending_captures(sensor=sensor, limit=batch_size):
            capture = process_capture(session)
            if capture.status == RadioCapture.STATUS_DONE:
                processed += 1
            else:
                errors += 1
                logger.warning(
                    "radio: capture failed for %s/%s -- %s",
                    sensor.slug,
                    session.session_id,
                    capture.error_message,
                )

    if processed or errors:
        logger.info("radio: processed %d capture(s), %d error(s)", processed, errors)


@shared_task(name="radio.tasks.archive_radio_captures")
def archive_radio_captures(pks):
    """Background counterpart to RadioCaptureAdmin.archive_action -- see
    ingestion.tasks.archive_ingested_files for why this runs as a task
    rather than inline (same reasoning, same ArchiveBatchPending split
    between the admin's synchronous pre-check and this task's race guard)."""
    from django.conf import settings

    from ingestion.archiving import ArchiveBatchPending, move_to_archive

    from .models import RadioCapture

    queryset = RadioCapture.objects.filter(pk__in=pks)
    try:
        archived, missing = move_to_archive(
            queryset,
            source_root=settings.RADIO_PCAP_ROOT,
            archive_subdir="radio_pcaps",
            path_field="pcap_path",
            eligible_statuses=[RadioCapture.STATUS_DONE],
        )
    except ArchiveBatchPending as exc:
        logger.warning("radio: archive batch refused -- %s", exc)
        return
    logger.info("radio: archived %d capture(s), %d missing", archived, missing)


@shared_task(name="radio.tasks.reclaim_radio_captures")
def reclaim_radio_captures(pks):
    """Background counterpart to RadioCaptureAdmin.reclaim_action -- see
    ingestion.tasks.archive_ingested_files for why this runs as a task."""
    from ingestion.archiving import reclaim_from_archive

    from .models import RadioCapture

    queryset = RadioCapture.objects.filter(pk__in=pks)
    deleted, missing, freed = reclaim_from_archive(
        queryset, archive_subdir="radio_pcaps", path_field="pcap_path"
    )
    logger.info("radio: reclaimed %d capture(s), freed %d bytes, %d missing", deleted, freed, missing)
