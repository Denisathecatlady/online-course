from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views


urlpatterns = [
    # Admin
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
