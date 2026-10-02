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
