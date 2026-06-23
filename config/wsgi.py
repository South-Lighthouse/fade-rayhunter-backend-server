import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_app = get_wsgi_application()

_webdav_app = None


def _get_webdav_app():
    global _webdav_app
    if _webdav_app is None:
        from ingestion.webdav import build_webdav_app
        _webdav_app = build_webdav_app()
    return _webdav_app


def application(environ, start_response):
    if environ.get("PATH_INFO", "").startswith("/webdav"):
        return _get_webdav_app()(environ, start_response)
    return django_app(environ, start_response)
