from django.core.management.base import BaseCommand, CommandError

from radio.models import CoveragePoint, RadioPacket
from sensors.models import Sensor


class Command(BaseCommand):
    help = (
        "One-off backfill: populates CoveragePoint for RadioPacket rows that predate the "
        "model, by scanning each sensor's packets once and deduplicating to ~111m grid "
        "cells per day. This is the one place that legitimately scans all of RadioPacket "
        "(tens of millions of rows) -- run it once, deliberately, during a quiet period. "
        "New captures get coverage incrementally from here on (radio/parsing.py); this "
        "command never needs to run again for the same sensor once it's caught up."
    )

    def add_arguments(self, parser):
        parser.add_argument("--sensor", help="Only backfill this sensor's slug. Omit to process all sensors.")
        parser.add_argument("--limit", type=int, default=None, help="Max number of sensors to process this run.")

    def handle(self, *args, **options):
        sensor_slug = options["sensor"]
        limit = options["limit"]

        if sensor_slug:
            try:
                sensors = [Sensor.objects.get(slug=sensor_slug)]
            except Sensor.DoesNotExist:
                raise CommandError(f"No sensor with slug '{sensor_slug}'")
        else:
            sensors = list(Sensor.objects.order_by("slug"))
            if limit is not None:
                sensors = sensors[:limit]

        for sensor in sensors:
            cells = set()
            rows = (
                RadioPacket.objects.filter(sensor=sensor, latitude__isnull=False, longitude__isnull=False)
                .values_list("qmdl_timestamp", "gps_timestamp", "latitude", "longitude")
                .iterator(chunk_size=5000)
            )
            for qmdl_timestamp, gps_timestamp, latitude, longitude in rows:
                reading_time = qmdl_timestamp or gps_timestamp
                if reading_time is None:
                    continue
                cells.add((reading_time.date(), round(latitude, 3), round(longitude, 3)))

            if cells:
                CoveragePoint.objects.bulk_create(
                    [CoveragePoint(sensor=sensor, date=d, latitude=lat, longitude=lon) for d, lat, lon in cells],
                    ignore_conflicts=True,
                )

            self.stdout.write(f"{sensor.slug}: {len(cells)} distinct coverage cell(s)")

        self.stdout.write(self.style.SUCCESS(f"Done. {len(sensors)} sensor(s) processed."))
