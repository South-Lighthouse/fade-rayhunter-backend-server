from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from radio.models import RadioCapture
from sensors.models import Sensor


class Command(BaseCommand):
    help = (
        "One-off backfill: populates RadioCapture.pcap_size for DONE captures created "
        "before that field existed, by stat'ing the file under RADIO_PCAP_ROOT (or "
        "ARCHIVE_ROOT/radio_pcaps, if already archived). Tolerant of a missing file -- "
        "logs a warning and leaves pcap_size null rather than crashing the batch."
    )

    def add_arguments(self, parser):
        parser.add_argument("--sensor", help="Only backfill this sensor's slug. Omit to consider all sensors.")
        parser.add_argument("--limit", type=int, default=None, help="Max number of captures to backfill.")

    def handle(self, *args, **options):
        sensor_slug = options["sensor"]
        limit = options["limit"]

        queryset = RadioCapture.objects.filter(status=RadioCapture.STATUS_DONE, pcap_size__isnull=True)
        if sensor_slug:
            try:
                sensor = Sensor.objects.get(slug=sensor_slug)
            except Sensor.DoesNotExist:
                raise CommandError(f"No sensor with slug '{sensor_slug}'")
            queryset = queryset.filter(session__sensor=sensor)
        if limit is not None:
            queryset = queryset[:limit]

        backfilled = missing = 0
        for capture in queryset.iterator():
            if not capture.pcap_path:
                missing += 1
                continue
            if capture.archived_at and not capture.reclaimed_at:
                root = Path(settings.ARCHIVE_ROOT) / "radio_pcaps"
            else:
                root = Path(settings.RADIO_PCAP_ROOT)
            full_path = root / capture.pcap_path
            try:
                capture.pcap_size = full_path.stat().st_size
            except FileNotFoundError:
                missing += 1
                self.stderr.write(self.style.WARNING(f"  missing on disk: {full_path}"))
                continue
            capture.save(update_fields=["pcap_size"])
            backfilled += 1

        self.stdout.write(self.style.SUCCESS(f"Backfilled {backfilled} capture(s). {missing} had no file on disk."))
