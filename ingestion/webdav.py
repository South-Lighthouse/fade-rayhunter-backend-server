import logging
import os

from wsgidav.dc.base_dc import BaseDomainController
from wsgidav.fs_dav_provider import FilesystemProvider
from wsgidav.wsgidav_app import WsgiDAVApp

logger = logging.getLogger(__name__)


class SensorDomainController(BaseDomainController):
    """
    Authenticates WebDAV requests against the Sensor table.

    URL layout:  /webdav/{sensor-slug}/...
    The sensor slug is used as the HTTP auth realm so each sensor
    gets its own credential prompt and cannot authenticate into a
    sibling sensor's path with its own credentials.
    """

    def __init__(self, wsgidav_app, config):
        super().__init__(wsgidav_app, config)

    def _sensor_slug_from_path(self, path_info):
        # wsgidav strips the /webdav mount prefix before calling the domain
        # controller, so path_info here is already /sensor-slug/...
        parts = [p for p in path_info.split("/") if p]
        return parts[0] if parts else None

    def get_domain_realm(self, path_info, environ):
        slug = self._sensor_slug_from_path(path_info)
        return slug or "fade"

    def require_authentication(self, realm, environ):
        return True

    def basic_auth_user(self, realm, user_name, password, environ):
        from django.conf import settings
        from sensors.models import Sensor

        # realm == sensor slug; only allow access when credentials match
        # exactly that sensor so a user cannot authenticate into a sibling path.
        try:
            sensor = Sensor.objects.get(slug=realm, is_active=True)
        except Sensor.DoesNotExist:
            return False

        if sensor.webdav_user == user_name and sensor.webdav_password == password:
            # Ensure the per-sensor upload directory exists before any write.
            os.makedirs(os.path.join(settings.UPLOAD_ROOT, sensor.slug), exist_ok=True)
            return True
        return False

    def digest_auth_user(self, realm, user_name, environ):
        # Digest auth not supported; returning None forces Basic.
        return None

    def supports_http_digest_auth(self):
        return False


def build_webdav_app():
    from django.conf import settings
    from sensors.models import Sensor

    upload_root = settings.UPLOAD_ROOT
    os.makedirs(upload_root, exist_ok=True)

    # Pre-create directories for all active sensors so listings work immediately.
    for sensor in Sensor.objects.filter(is_active=True):
        os.makedirs(os.path.join(upload_root, sensor.slug), exist_ok=True)

    config = {
        "provider_mapping": {
            "/webdav": FilesystemProvider(upload_root, readonly=False),
        },
        "http_authenticator": {
            "domain_controller": SensorDomainController,
            "accept_basic": True,
            "accept_digest": False,
            "default_to_digest": False,
        },
        "verbose": 0,
        "logging": {"enable_loggers": []},
        "property_manager": True,
        "lock_storage": True,
    }

    return WsgiDAVApp(config)
