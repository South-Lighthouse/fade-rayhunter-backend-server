import secrets
from django.db import models
from django.utils.text import slugify


class SensorType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    default_ip_address = models.CharField(max_length=45, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Sensor(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    sensor_type = models.ForeignKey(
        SensorType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sensors",
    )
    webdav_user = models.CharField(max_length=255)
    webdav_password = models.CharField(max_length=255)
    api_key = models.CharField(max_length=64, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.api_key:
            self.api_key = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def upload_path(self):
        from django.conf import settings
        import os
        return os.path.join(settings.UPLOAD_ROOT, self.slug)
