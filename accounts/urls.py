from django.urls import path
from django.contrib.auth import views as auth_views

urlpatterns = [
    path(
        "prihlaseni/",
        auth_views.LoginView.as_view(template_name="accounts/login.html"),
        name="login",
    ),
    path(
        "odhlaseni/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
]

