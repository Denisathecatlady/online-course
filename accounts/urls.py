from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = "accounts"

urlpatterns = [
    # Přihlášení/odhlášení/změna hesla teď obsluhuje allauth.
    # Ponecháváme staré názvy jako přesměrování, aby nikde nespadly odkazy
    # `accounts:login` / `accounts:logout` / `accounts:password_change`.
    path(
        "prihlaseni/",
        RedirectView.as_view(pattern_name="account_login", query_string=True),
        name="login",
    ),
    path(
        "odhlaseni/",
        RedirectView.as_view(pattern_name="account_logout"),
        name="logout",
    ),
    path(
        "zmena-hesla/",
        RedirectView.as_view(pattern_name="account_change_password"),
        name="password_change",
    ),

    # Vlastní stránky účtu
    path("prehled/", views.overview, name="overview"),
    path("profil/", views.profile_view, name="profile"),
    path("profil/upravit/", views.profile_edit, name="profile_edit"),
    path("moji-psi/", views.dogs, name="dogs"),
    path("moji-psi/pridat/", views.dog_add, name="dog_add"),
    path("moji-psi/<int:pk>/upravit/", views.dog_edit, name="dog_edit"),
    path("moji-psi/<int:pk>/smazat/", views.dog_delete, name="dog_delete"),
    path("rezervace-treninku/", views.reservations, name="reservations"),
    path("kurzy/", views.courses_overview, name="courses"),
    path("moje-kurzy/", views.my_courses, name="my_courses"),
    path("objednavky/", views.order_history, name="order_history"),
    path("objednavky/<int:pk>/", views.order_detail, name="order_detail"),
    path("objednavky/<int:pk>/vratit/", views.request_return, name="request_return"),
    path("faktury/", views.invoices, name="invoices"),
    path("faktury/<int:pk>/stahnout/", views.download_invoice, name="invoice_download"),
    path("nastaveni/", views.account_settings, name="settings"),
]
