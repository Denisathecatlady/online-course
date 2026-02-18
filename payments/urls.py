from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [
    path("stripe-webhook/", views.stripe_webhook, name="stripe-webhook"),
    path("checkout/", views.checkout, name="checkout"),
    path("success/", views.success, name="success"),
    path("cancel/", views.cancel, name="cancel"),
    path("webhook/", views.stripe_webhook, name="webhook"),
    path("cart/", views.cart_detail, name="cart_detail"),
    path(
        "cart/add/<slug:product_slug>/<slug:plan_code>/",
        views.add_course_to_cart,
        name="add_course_to_cart"
    ),
    path("cart/remove/<int:item_id>/", views.remove_from_cart, name="remove_from_cart"),
    # seznamy
    path("kurzy/", views.course_list, name="course_list"),
    path("voditka/", views.physical_list, name="physical_list"),

    # detail
    path("kurzy/<slug:slug>/", views.course_detail, name="course_detail"),
    path("voditka/<slug:slug>/", views.physical_detail, name="physical_detail"),
]
