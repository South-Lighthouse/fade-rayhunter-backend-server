from rest_framework import serializers
from .models import TelemetryRecord


class TelemetryRecordSerializer(serializers.ModelSerializer):
    sensor_slug = serializers.CharField(source="sensor.slug", read_only=True)

    class Meta:
        model = TelemetryRecord
        fields = [
            "id", "sensor_slug", "event_type", "message",
            "device_timestamp", "ip_address", "received_at",
        ]
