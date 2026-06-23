from rest_framework import serializers
from .models import TelemetryRecord


class TelemetryRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryRecord
        fields = ["id", "device_id", "sensor", "payload", "ip_address", "received_at"]
        read_only_fields = ["id", "ip_address", "received_at"]
