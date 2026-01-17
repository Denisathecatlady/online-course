from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("stripe-webhook/", views.stripe_webhook, name="stripe-webhook"),
    path("checkout/<slug:plan_code>/", views.checkout, name="checkout"),
    path("success/", views.success, name="success"),
    path("cancel/", views.cancel, name="cancel"),
    path("webhook/", views.stripe_webhook, name="webhook"),
]
