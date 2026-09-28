from django.core.management.base import BaseCommand, CommandError

from captures.parsing import discover_pending_sessions, process_session
from sensors.models import Sensor


class Command(BaseCommand):
    help = (
        "Parses already-uploaded Rayhunter capture sessions (general log + GPS) into "
        "MonitoringSession/RayhunterLogEntry rows. Discovers unprocessed sessions by "
        "scanning UPLOAD_ROOT/<sensor.slug>/ for <id>.ndjson files not yet imported "
        "-- safe to re-run, already-processed sessions are skipped."
    )

    def add_arguments(self, parser):
        parser.add_argument("--sensor", help="Only process this sensor's slug. Omit to process all sensors.")
        parser.add_argument("--session-id", help="Only process this specific session id (requires --sensor).")
        parser.add_argument("--limit", type=int, default=None, help="Max number of sessions to process per sensor.")

    def handle(self, *args, **options):
        sensor_slug = options["sensor"]
        session_id = options["session_id"]
        limit = options["limit"]

        if session_id and not sensor_slug:
            raise CommandError("--session-id requires --sensor")

        if sensor_slug:
            sensors = list(Sensor.objects.filter(slug=sensor_slug))
            if not sensors:
                raise CommandError(f"No sensor with slug '{sensor_slug}'")
        else:
            sensors = list(Sensor.objects.all())

        total_processed = 0
        total_skipped = 0

        for sensor in sensors:
            session_ids = [session_id] if session_id else discover_pending_sessions(sensor, limit=limit)
            if not session_ids:
                continue

            self.stdout.write(f"{sensor.slug}: {len(session_ids)} session(s) to process")
            for sid in session_ids:
                try:
                    session = process_session(sensor, sid)
                except ValueError as exc:
                    total_skipped += 1
                    self.stderr.write(self.style.WARNING(f"  {sensor.slug}/{sid}: skipped -- {exc}"))
                    continue

                count = session.log_entries.count()
                alerts = session.log_entries.filter(is_alert=True).count()
                total_processed += 1
                self.stdout.write(f"  {sensor.slug}/{sid}: {count} entries ({alerts} alerts)")

        self.stdout.write(
            self.style.SUCCESS(f"Done. {total_processed} session(s) processed, {total_skipped} skipped.")
        )
