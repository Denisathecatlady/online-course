from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.http import Http404
import logging

_honeypot_log = logging.getLogger("admin.honeypot")


def _admin_honeypot(request, *args, **kwargs):
    """Zachytí boty zkoušející standardní /admin/ URL a zaloguje pokus."""
    _honeypot_log.warning(
        "Honeypot hit | IP: %s | path: %s | UA: %.120s",
        request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "-")),
        request.path,
        request.META.get("HTTP_USER_AGENT", "-"),
    )
    raise Http404


# Vzhled administrace – interní systém CalmDog
admin.site.site_header = "CalmDog – administrace"
admin.site.site_title = "CalmDog administrace"
admin.site.index_title = "Správa e-shopu a kurzů"


urlpatterns = [
    # Honeypot – zachytí pokusy na standardní /admin/ URL
    re_path(r"^admin/", _admin_honeypot),

    # Skutečný admin na tajné URL (nastaveno v DJANGO_ADMIN_URL env var)
    path(settings.ADMIN_URL, admin.site.urls),

    # Courses (HLAVNÍ APPKA – namespace)
    path(
        "",
        include(("courses.urls", "courses"), namespace="courses")
    ),

    # Accounts
    path("ucty/", include("accounts.urls")),

    # Payments (namespace)
    path(
        "payments/",
        include(("payments.urls", "payments"), namespace="payments")
    ),

    # Hotel pro psy a kočky
    path("hotel/", include(("hotel.urls", "hotel"), namespace="hotel")),

    # Shop (vodítka)
    path("voditka/", include("shop.urls")),

    # Reset hesla
    path(
        "ucty/reset-hesla/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/registration/password_reset_form.html"
        ),
        name="password_reset",
    ),

    path(
        "ucty/reset-hesla/odeslano/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="accounts/registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),

    path(
        "ucty/reset-hesla/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),

    path(
        "ucty/reset-hesla/hotovo/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="accounts/registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]


# MEDIA bez S3 storage
if not settings.USE_S3_STORAGE:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
