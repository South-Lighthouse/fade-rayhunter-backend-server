from django.db import models


class TelemetryRecord(models.Model):
    sensor = models.ForeignKey(
        "sensors.Sensor",
        on_delete=models.SET_NULL,
        null=True,
        related_name="telemetry",
    )
    event_type = models.CharField(max_length=100)
    message = models.TextField(blank=True)
    device_timestamp = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    raw_payload = models.JSONField()

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.sensor.slug} / {self.event_type} @ {self.received_at}"
