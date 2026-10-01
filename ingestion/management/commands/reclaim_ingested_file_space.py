from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum
from django.template.defaultfilters import filesizeformat

from ingestion.archiving import reclaim_from_archive
from ingestion.models import IngestedFile
from sensors.models import Sensor


class Command(BaseCommand):
    help = (
        "Step B of the archive/pickup/reclaim flow: deletes the on-disk copy under "
        "ARCHIVE_ROOT/uploads for IngestedFile rows that are archived but not yet reclaimed, "
        "and stamps reclaimed_at. Only run this after confirming the files have already been "
        "pulled off the server -- it deletes bytes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--sensor", help="Only reclaim this sensor's slug. Omit to consider all sensors.")
        parser.add_argument("--limit", type=int, default=None, help="Max number of files to reclaim.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted and how much space freed, without touching disk.",
        )

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

        candidates = queryset.filter(archived_at__isnull=False, reclaimed_at__isnull=True)
        if limit is not None:
            candidates = IngestedFile.objects.filter(pk__in=list(candidates.values_list("pk", flat=True)[:limit]))

        if options["dry_run"]:
            total = candidates.aggregate(total=Sum("file_size"))["total"] or 0
            self.stdout.write(
                f"Dry run: would delete {candidates.count()} file(s), freeing {filesizeformat(total)}."
            )
            return

        deleted, missing, freed = reclaim_from_archive(candidates, archive_subdir="uploads", path_field="relative_path")
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted} file(s), freed {filesizeformat(freed)}. {missing} were already missing.")
        )
