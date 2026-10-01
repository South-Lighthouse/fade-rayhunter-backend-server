from django.core.management.base import BaseCommand, CommandError

from captures.models import MonitoringSession
from radio.models import RadioCapture
from radio.parsing import discover_pending_captures, process_capture
from sensors.models import Sensor


class Command(BaseCommand):
    help = (
        "Converts QMDL(+GPS) for monitoring sessions left at "
        "IngestedFile.STATUS_AWAITING_FURTHER_PROCESSING into a PCAP (via qmdl2pcap) and "
        "parses it with tshark into RadioPacket rows -- safe to re-run, sessions that "
        "already have a RadioCapture are skipped."
    )

    def add_arguments(self, parser):
        parser.add_argument("--sensor", help="Only process this sensor's slug. Omit to process all sensors.")
        parser.add_argument("--session-id", help="Only process this specific session id (requires --sensor).")
        parser.add_argument("--limit", type=int, default=None, help="Max number of sessions to process.")

    def handle(self, *args, **options):
        sensor_slug = options["sensor"]
        session_id = options["session_id"]
        limit = options["limit"]

        if session_id and not sensor_slug:
            raise CommandError("--session-id requires --sensor")

        sensor = None
        if sensor_slug:
            try:
                sensor = Sensor.objects.get(slug=sensor_slug)
            except Sensor.DoesNotExist:
                raise CommandError(f"No sensor with slug '{sensor_slug}'")

        if session_id:
            sessions = list(MonitoringSession.objects.filter(sensor=sensor, session_id=session_id))
            if not sessions:
                raise CommandError(f"No monitoring session '{session_id}' for sensor '{sensor_slug}'")
        else:
            sessions = discover_pending_captures(sensor=sensor, limit=limit)

        if not sessions:
            self.stdout.write("Nothing to process.")
            return

        self.stdout.write(f"{len(sessions)} session(s) to process")

        total_done = 0
        total_errors = 0
        for session in sessions:
            capture = process_capture(session)
            label = f"{session.sensor.slug}/{session.session_id}"
            if capture.status == RadioCapture.STATUS_DONE:
                total_done += 1
                self.stdout.write(f"  {label}: {capture.packet_count} packet(s)")
            else:
                total_errors += 1
                self.stderr.write(self.style.WARNING(f"  {label}: error -- {capture.error_message}"))

        self.stdout.write(
            self.style.SUCCESS(f"Done. {total_done} capture(s) processed, {total_errors} error(s).")
        )
