from django.db import models


class TelemetryRecord(models.Model):
    sensor = models.ForeignKey(
        "sensors.Sensor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="telemetry",
    )
    device_id = models.CharField(max_length=255, blank=True)
    payload = models.JSONField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.device_id or 'unknown'} @ {self.received_at}"
