from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string

from dashboard.reports import build_country_report
from dashboard.svg_charts import render_daily_series_svg
from sensors.models import Country


class Command(BaseCommand):
    help = (
        "Generate a printable HTML activity report for a country's sensors over a "
        "date range. Prints to stdout, or writes to a file with --output. This is "
        "the automation entry point: a future scheduled task can call the same "
        "build_country_report() this command uses and decide where the HTML goes."
    )

    def add_arguments(self, parser):
        parser.add_argument("country", help="Country code or name, as shown in the admin.")
        parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD (inclusive).")
        parser.add_argument("--end", required=True, help="End date, YYYY-MM-DD (inclusive).")
        parser.add_argument(
            "--stale-hours",
            type=int,
            default=None,
            help="Override the staleness threshold in hours (defaults to SENSOR_STALE_HOURS).",
        )
        parser.add_argument("--output", help="Write HTML to this file instead of stdout.")

    def handle(self, *args, **options):
        identifier = options["country"]
        country = (
            Country.objects.filter(code__iexact=identifier).first()
            or Country.objects.filter(name__iexact=identifier).first()
        )
        if country is None:
            raise CommandError(f"No country matches '{identifier}' (checked code and name).")

        try:
            start_date = datetime.strptime(options["start"], "%Y-%m-%d").date()
            end_date = datetime.strptime(options["end"], "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(f"Invalid date: {exc}")

        if end_date < start_date:
            raise CommandError("--end must not be before --start.")

        stale_hours = options["stale_hours"] or getattr(settings, "SENSOR_STALE_HOURS", 96)

        context = build_country_report(country, start_date, end_date, stale_hours)
        context["chart_svg"] = render_daily_series_svg(
            context["daily_series"], label=f"Uploads per day — {country.name}"
        )
        html = render_to_string("dashboard/country_report_standalone.html", context)

        if options["output"]:
            with open(options["output"], "w") as fh:
                fh.write(html)
            self.stdout.write(self.style.SUCCESS(f"Wrote report to {options['output']}"))
        else:
            self.stdout.write(html)
