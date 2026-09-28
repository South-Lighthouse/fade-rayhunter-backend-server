from django.db import models


class MonitoringSession(models.Model):
    sensor = models.ForeignKey(
        "sensors.Sensor", on_delete=models.CASCADE, related_name="monitoring_sessions"
    )
    session_id = models.CharField(max_length=32)

    rayhunter_version = models.CharField(max_length=50, blank=True)
    system_os = models.CharField(max_length=100, blank=True)
    arch = models.CharField(max_length=50, blank=True)
    report_version = models.IntegerField(null=True, blank=True)
    analyzers = models.JSONField(default=list, blank=True)

    has_gps = models.BooleanField(default=False)

    general_log_file = models.ForeignKey(
        "ingestion.IngestedFile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    gps_log_file = models.ForeignKey(
        "ingestion.IngestedFile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    qmdl_file = models.ForeignKey(
        "ingestion.IngestedFile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ["sensor", "session_id"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sensor.slug}/{self.session_id}"


class RayhunterLogEntry(models.Model):
    SEVERITY_INFORMATIONAL = "Informational"
    SEVERITY_LOW = "Low"
    SEVERITY_MEDIUM = "Medium"
    SEVERITY_HIGH = "High"
    SEVERITY_CHOICES = [
        (SEVERITY_INFORMATIONAL, "Informational"),
        (SEVERITY_LOW, "Low"),
        (SEVERITY_MEDIUM, "Medium"),
        (SEVERITY_HIGH, "High"),
    ]

    session = models.ForeignKey(MonitoringSession, on_delete=models.CASCADE, related_name="log_entries")
    sensor = models.ForeignKey(
        "sensors.Sensor", on_delete=models.CASCADE, related_name="rayhunter_log_entries"
    )

    line_number = models.PositiveIntegerField()
    qmdl_timestamp = models.DateTimeField(null=True, blank=True)
    gps_timestamp = models.DateTimeField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    is_alert = models.BooleanField(default=False)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, blank=True)
    log_entry = models.TextField(blank=True)
    raw_payload = models.JSONField()

    class Meta:
        ordering = ["session", "line_number"]
        indexes = [
            models.Index(fields=["sensor", "qmdl_timestamp"]),
            models.Index(fields=["sensor", "is_alert"]),
        ]

    def __str__(self):
        return f"{self.sensor.slug}/{self.session.session_id}#{self.line_number}"
