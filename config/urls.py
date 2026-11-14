from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include
from two_factor.urls import urlpatterns as tf_urls

admin.site.site_title = "FADe dashboard"


def admin_index_redirect(request):
    """
    Sends logged-in users straight to the sensor dashboard instead of
    Django's default admin index. Registered as a plain (non-include) path
    BEFORE admin.site.urls below, so it only matches the exact "/admin/"
    URL -- every deeper admin URL falls through untouched to the real
    admin.site.urls entry on the next line. Wrapped in admin.site.admin_view
    so an anonymous hit still goes through the normal (2FA-aware) login
    flow first, landing here again afterwards via `next`.
    """
    return redirect("admin:sensors_sensor_dashboard")


urlpatterns = [
    path("", include(tf_urls)),
    path("admin/", admin.site.admin_view(admin_index_redirect)),
    path("admin/", admin.site.urls),
    path("api/telemetry/", include("telemetry.urls")),
]
