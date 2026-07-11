import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("sensors", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TelemetryRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(max_length=100)),
                ("message", models.TextField(blank=True)),
                ("device_timestamp", models.DateTimeField(blank=True, null=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("raw_payload", models.JSONField()),
                (
                    "sensor",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="telemetry",
                        to="sensors.sensor",
                    ),
                ),
            ],
            options={
                "ordering": ["-received_at"],
            },
        ),
    ]
