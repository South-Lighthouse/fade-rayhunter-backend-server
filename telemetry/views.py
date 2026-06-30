from datetime import datetime, timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import TelemetryRecord
from .serializers import TelemetryRecordSerializer


def _authenticate_sensor(request):
    """
    Extracts the Bearer token from Authorization header and returns the
    matching active Sensor, or None if the token is missing or invalid.
    """
    auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        return None
    api_key = auth[len("Bearer "):]
    from sensors.models import Sensor
    try:
        return Sensor.objects.get(api_key=api_key, is_active=True)
    except Sensor.DoesNotExist:
        return None


def _parse_device_timestamp(value):
    if not value:
        return None
    try:
        # Python 3.11+ handles the Z suffix natively
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


class TelemetryIngestView(APIView):
    """
    POST /api/telemetry/

    Accepts a JSON event from a Rayhunter companion Android app.
    Authentication: Authorization: Bearer <sensor-api-key>

    Expected payload:
        {
            "timestamp":  "2026-06-27T14:30:45Z",
            "sensor_id":  "my-sensor-001",
            "type":       "GPS OK",
            "message":    "40.123456, -74.567890"
        }
    """

    permission_classes = [AllowAny]  # Auth is handled manually via API key below

    def post(self, request):
        sensor = _authenticate_sensor(request)
        if sensor is None:
            return Response(
                {"detail": "Invalid or missing API key."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        ip = (
            request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR")
        )

        record = TelemetryRecord(
            sensor=sensor,
            event_type=request.data.get("type", ""),
            message=request.data.get("message", ""),
            device_timestamp=_parse_device_timestamp(request.data.get("timestamp")),
            ip_address=ip or None,
            raw_payload=request.data,
        )
        record.save()

        return Response(
            TelemetryRecordSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )
