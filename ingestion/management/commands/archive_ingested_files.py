from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ingestion.archiving import ArchiveBatchPending, move_to_archive
from ingestion.models import IngestedFile
from sensors.models import Sensor

ELIGIBLE_ARCHIVE_STATUSES = [IngestedFile.STATUS_DONE, IngestedFile.STATUS_ERROR]


class Command(BaseCommand):
    help = (
        "Step A of the archive/pickup/reclaim flow: moves eligible IngestedFile files "
        "(status done/error -- never pending/processing/awaiting_further_processing) from "
        "UPLOAD_ROOT into ARCHIVE_ROOT/uploads and stamps archived_at. Refuses entirely if "
        "a previous batch (uploads or radio captures) hasn't been reclaimed yet."
    )

    def add_arguments(self, parser):
        parser.add_argument("--sensor", help="Only archive this sensor's slug. Omit to consider all sensors.")
        parser.add_argument("--limit", type=int, default=None, help="Max number of files to archive.")

    def handle(self, *args, **options):
        sensor_slug = options["sensor"]
        limit = options["limit"]

        queryset = IngestedFile.objects.all()
        if sensor_slug:
            try:
                sensor = Sensor.objects.get(slug=sensor_slug)
            except Sensor.DoesNotExist:
                raise CommandError(f"No sensor with slug '{sensor_slug}'")
            queryset = queryset.filter(sensor=sensor)
        if limit is not None:
            eligible_ids = list(
                queryset.filter(status__in=ELIGIBLE_ARCHIVE_STATUSES, archived_at__isnull=True)
                .values_list("pk", flat=True)[:limit]
            )
            queryset = queryset.filter(pk__in=eligible_ids)

        try:
            archived, missing = move_to_archive(
                queryset,
                source_root=settings.UPLOAD_ROOT,
                archive_subdir="uploads",
                path_field="relative_path",
                eligible_statuses=ELIGIBLE_ARCHIVE_STATUSES,
            )
        except ArchiveBatchPending as exc:
            raise CommandError(str(exc))

        self.stdout.write(self.style.SUCCESS(f"Archived {archived} file(s)."))
        if missing:
            self.stdout.write(
                self.style.WARNING(f"{missing} had no file on disk (DB-only, marked archived anyway).")
            )
