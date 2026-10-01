from django.db import models


class IngestedFile(models.Model):
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_AWAITING_FURTHER_PROCESSING = "awaiting_further_processing"
    STATUS_DONE = "done"
    STATUS_ERROR = "error"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_AWAITING_FURTHER_PROCESSING, "Awaiting further processing"),
        (STATUS_DONE, "Done"),
        (STATUS_ERROR, "Error"),
    ]

    sensor = models.ForeignKey(
        "sensors.Sensor", on_delete=models.CASCADE, related_name="ingested_files"
    )
    filename = models.CharField(max_length=255)
    relative_path = models.CharField(max_length=512)
    file_size = models.BigIntegerField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    reclaimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        unique_together = ["sensor", "relative_path"]

    def __str__(self):
        return f"{self.sensor.slug}/{self.filename}"
