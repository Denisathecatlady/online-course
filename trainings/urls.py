"""
URL konfigurace rezervačního systému (namespace "trainings").

Poznámka k pořadí: konkrétní cesty `rezervace/slot/…`, `rezervace/hotovo/…`
a `rezervace/<pk>/zrusit/` jsou uvedené PŘED obecnou `rezervace/<slug>/`,
aby je Django zachytil dřív než lokalitu podle slugu.
"""

from django.urls import path

from . import views

app_name = "trainings"

urlpatterns = [
    # Karta v profilu
    path("", views.my_reservations, name="my_reservations"),

    # Rezervační flow
    path("rezervace/", views.select_location, name="select_location"),
    path("rezervace/slot/<int:slot_id>/", views.book_slot, name="book_slot"),
    path("rezervace/hotovo/<int:pk>/", views.reservation_success, name="reservation_success"),
    path("rezervace/<int:pk>/zrusit/", views.cancel_reservation, name="cancel_reservation"),
    path("rezervace/<slug:slug>/", views.available_slots, name="available_slots"),

    # Google Calendar OAuth (admin – jednorázové připojení trenéra)
    path("google/pripojit/<int:trainer_id>/", views.google_oauth_start, name="google_oauth_start"),
    path("google/callback/", views.google_oauth_callback, name="google_oauth_callback"),
]
