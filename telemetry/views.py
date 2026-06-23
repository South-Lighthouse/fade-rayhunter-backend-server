from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TelemetryRecord
from .serializers import TelemetryRecordSerializer


class TelemetryIngestView(APIView):
    """
    POST /api/telemetry/ingest/
    Accepts a JSON payload from a device in the field.
    Authentication is intentionally open (AllowAny) — devices may not have
    Django credentials.  Rate-limit this endpoint at the nginx/load-balancer
    level in production.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR")
        )

        record = TelemetryRecord(
            payload=request.data,
            ip_address=ip or None,
            device_id=request.data.get("device_id", ""),
        )

        sensor_slug = request.data.get("sensor")
        if sensor_slug:
            from sensors.models import Sensor
            try:
                record.sensor = Sensor.objects.get(slug=sensor_slug, is_active=True)
            except Sensor.DoesNotExist:
                pass

        record.save()

        return Response(
            TelemetryRecordSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )
