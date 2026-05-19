from django.urls import path
from . import views

app_name = "hotel"

urlpatterns = [
    path("", views.hotel_home, name="home"),
    path("rezervace/", views.reservation_form, name="reservation_form"),
    path("rezervace/dekujeme/", views.reservation_success, name="reservation_success"),
    path("api/volne-terminy/", views.available_dates_json, name="available_dates"),
]
