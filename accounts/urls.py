from django.urls import path
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from . import views

app_name = "accounts"

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
    path("profil/", views.profile_view, name="profile"),
    path("moje-kurzy/", views.my_courses, name="my_courses"),
    path("objednavky/", views.order_history, name="order_history"),
    path("objednavky/<int:pk>/", views.order_detail, name="order_detail"),
    path("zmena-hesla/", 
     auth_views.PasswordChangeView.as_view(
         template_name="accounts/password_change.html",
         success_url=reverse_lazy("accounts:profile"),
         extra_context={"account_section": "profile"},
     ),
     name="password_change"),
]
