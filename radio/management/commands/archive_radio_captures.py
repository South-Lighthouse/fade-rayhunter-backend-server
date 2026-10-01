from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ingestion.archiving import ArchiveBatchPending, move_to_archive
from radio.models import RadioCapture
from sensors.models import Sensor


class Command(BaseCommand):
    help = (
        "Step A of the archive/pickup/reclaim flow: moves eligible RadioCapture PCAPs "
        "(status done) from RADIO_PCAP_ROOT into ARCHIVE_ROOT/radio_pcaps and stamps "
        "archived_at. Refuses entirely if a previous batch (uploads or radio captures) "
        "hasn't been reclaimed yet."
    )

    def add_arguments(self, parser):
        parser.add_argument("--sensor", help="Only archive this sensor's slug. Omit to consider all sensors.")
        parser.add_argument("--limit", type=int, default=None, help="Max number of captures to archive.")

    def handle(self, *args, **options):
        sensor_slug = options["sensor"]
        limit = options["limit"]

        queryset = RadioCapture.objects.all()
        if sensor_slug:
            try:
                sensor = Sensor.objects.get(slug=sensor_slug)
            except Sensor.DoesNotExist:
                raise CommandError(f"No sensor with slug '{sensor_slug}'")
            queryset = queryset.filter(session__sensor=sensor)
        if limit is not None:
            eligible_ids = list(
                queryset.filter(status=RadioCapture.STATUS_DONE, archived_at__isnull=True)
                .values_list("pk", flat=True)[:limit]
            )
            queryset = queryset.filter(pk__in=eligible_ids)

        try:
            archived, missing = move_to_archive(
                queryset,
                source_root=settings.RADIO_PCAP_ROOT,
                archive_subdir="radio_pcaps",
                path_field="pcap_path",
                eligible_statuses=[RadioCapture.STATUS_DONE],
            )
        except ArchiveBatchPending as exc:
            raise CommandError(str(exc))

        self.stdout.write(self.style.SUCCESS(f"Archived {archived} capture(s)."))
        if missing:
            self.stdout.write(
                self.style.WARNING(f"{missing} had no PCAP file on disk (DB-only, marked archived anyway).")
            )
