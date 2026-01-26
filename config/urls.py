"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views




urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),

    path("", include("courses.urls")),
    path("ucty/", include("accounts.urls")),
    path("payments/", include(("payments.urls", "payments"), namespace="payments")),

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




if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
