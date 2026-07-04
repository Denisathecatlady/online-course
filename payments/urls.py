from django.urls import path
from . import views

app_name = "payments"

urlpatterns = [

    # Stripe
    path("stripe-webhook/", views.stripe_webhook, name="stripe_webhook"),

    # Košík
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/remove/<int:item_id>/", views.remove_from_cart, name="remove_from_cart"),
    path("cart/qty/<int:item_id>/", views.update_cart_quantity, name="update_cart_quantity"),

    # Slevový kupón
    path("cart/apply-coupon/", views.apply_coupon, name="apply_coupon"),
    path("cart/remove-coupon/", views.remove_coupon, name="remove_coupon"),

    # Přidání do košíku
    path(
        "add-course/<int:plan_id>/",
        views.add_course_to_cart,
        name="add_course_to_cart"
    ),
    path(
        "add-variant/<int:variant_id>/",
        views.add_variant_to_cart,
        name="add_variant_to_cart"
    ),
    path(
        "add-bundle/<int:variant_id>/",
        views.add_bundle_to_cart,
        name="add_bundle_to_cart"
    ),

    # Checkout
    path("checkout/", views.checkout, name="checkout"),
    path("contact/", views.checkout, name="contact_details"),
    path("success/", views.success, name="success"),
    path("cancel/", views.cancel, name="cancel"),

    # Kurzy
    path("kurzy/", views.course_list, name="course_list"),
    path("kurz/<slug:slug>/", views.course_detail, name="course_detail"),

    # Doprava
    path("shipping/", views.shipping, name="shipping"),

    # Uvítací sleva
    path("welcome-coupon/", views.claim_welcome_coupon, name="claim_welcome_coupon"),
]
