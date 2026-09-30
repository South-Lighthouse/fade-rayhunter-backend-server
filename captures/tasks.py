import logging

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name="captures.tasks.process_pending_monitoring_sessions")
def process_pending_monitoring_sessions():
    """
    Periodically parses newly-uploaded monitoring sessions (general log +
    GPS) for every active sensor -- the same logic the
    process_monitoring_sessions management command wraps.

    Bounded per sensor per run via SESSION_PROCESSING_BATCH_SIZE so one
    invocation can't run unboundedly long on a large backlog; leftover
    sessions are simply picked up on the next scheduled run.
    """
    from sensors.models import Sensor

    from .parsing import discover_pending_sessions, process_session

    batch_size = getattr(settings, "SESSION_PROCESSING_BATCH_SIZE", 50)
    processed = 0
    errors = 0

    for sensor in Sensor.objects.filter(is_active=True):
        for session_id in discover_pending_sessions(sensor, limit=batch_size):
            try:
                process_session(sensor, session_id)
                processed += 1
            except ValueError as exc:
                errors += 1
                logger.warning("captures: skipped %s/%s -- %s", sensor.slug, session_id, exc)

    if processed or errors:
        logger.info("captures: processed %d session(s), %d error(s)", processed, errors)
