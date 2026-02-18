import os
import stripe

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import EmailMessage
from django.db import transaction
from django.contrib.auth.decorators import login_required
from .models import CoursePlan, Order, CourseAccess, Product, OrderItem
from .services.cart import get_or_create_cart
from payments.services.invoice import generate_invoice_pdf, assign_invoice_number
from django.shortcuts import render, get_object_or_404
from .models import Product, CoursePlan

import logging

logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()


# =====================================================
# KOŠÍK
# =====================================================


def add_course_to_cart(request, product_slug, plan_code):
    product = get_object_or_404(Product, slug=product_slug, product_type="course")
    plan = get_object_or_404(CoursePlan, code=plan_code)

    cart = get_or_create_cart(request)

    OrderItem.objects.get_or_create(
        order=cart,
        product=product,
        plan=plan,
        defaults={
            "quantity": 1,
            "price_at_purchase": plan.price_czk
        }
    )

    return redirect("payments:cart_detail")




def cart_detail(request):
    cart = get_or_create_cart(request)

    cart = Order.objects.prefetch_related(
        "items__product",
        "items__plan"
    ).get(id=cart.id)

    items = cart.items.all()

    return render(request, "payments/cart.html", {
        "cart": cart,
        "items": items
    })


# =====================================================
# CHECKOUT
# =====================================================


@require_http_methods(["GET", "POST"])
def checkout(request):

    if not stripe.api_key:
        return HttpResponseBadRequest("Chybí STRIPE_SECRET_KEY.")

    cart = get_or_create_cart(request)

    cart = Order.objects.prefetch_related(
        "items__product",
        "items__plan"
    ).get(id=cart.id)

    if not cart.items.exists():
        return HttpResponseBadRequest("Košík je prázdný.")


    if request.method == "GET":
        return render(
            request,
            "payments/checkout_form.html",
            {
                "cart": cart,
                "items": cart.items.all(),
            },
        )

    # Uložení fakturačních údajů
    cart.buyer_email = request.POST.get("email", "").strip()
    cart.first_name = request.POST.get("first_name", "").strip()
    cart.last_name = request.POST.get("last_name", "").strip()
    cart.street = request.POST.get("street", "").strip()
    cart.city = request.POST.get("city", "").strip()
    cart.zip_code = request.POST.get("zip_code", "").strip()
    cart.country = request.POST.get("country", "CZ").strip()
    cart.newsletter_opt_in = bool(request.POST.get("newsletter"))
    cart.status = Order.Status.PENDING
    cart.save()

    line_items = []

    for item in cart.items.all():
        line_items.append({
            "quantity": item.quantity,
            "price_data": {
                "currency": "czk",
                "unit_amount": int(item.price_at_purchase * 100),
                "product_data": {
                    "name": item.product.name,
                },
            },
        })

    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=cart.buyer_email,
        line_items=line_items,
        success_url=request.build_absolute_uri("/payments/success/"),
        cancel_url=request.build_absolute_uri("/payments/cancel/"),
        metadata={"order_id": str(cart.id)},
    )

    cart.stripe_checkout_session_id = session.id
    cart.save(update_fields=["stripe_checkout_session_id"])

    return redirect(session.url)


# =====================================================
# SUCCESS / CANCEL
# =====================================================

@require_GET
def success(request):
    return render(request, "payments/success.html")


@require_GET
def cancel(request):
    return render(request, "payments/cancel.html")


# =====================================================
# STRIPE WEBHOOK
# =====================================================

@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=endpoint_secret,
        )
    except Exception:
        return HttpResponseBadRequest("Invalid webhook")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order_id = session.get("metadata", {}).get("order_id")

        if not order_id:
            return HttpResponse(status=200)

        try:
            order = Order.objects.prefetch_related("items__product", "items__plan").get(id=order_id)
        except Order.DoesNotExist:
            return HttpResponse(status=200)

        if order.status == Order.Status.PAID:
            return HttpResponse(status=200)

        with transaction.atomic():

            order.status = Order.Status.PAID
            order.stripe_payment_intent_id = session.get("payment_intent", "")
            order.save(update_fields=["status", "stripe_payment_intent_id"])

            assign_invoice_number(order)

            invoice_file = generate_invoice_pdf(order)
            order.invoice_pdf.save(invoice_file.name, invoice_file)
            order.save(update_fields=["invoice_pdf"])

        User = get_user_model()
        user, created = User.objects.get_or_create(
            email=order.buyer_email,
            defaults={
                "username": order.buyer_email,
                "first_name": order.first_name,
                "last_name": order.last_name,
            },
        )

        if created:
            user.set_unusable_password()
            user.save()

        order.user = user
        order.save(update_fields=["user"])

        # Vytvoření přístupu ke kurzům podle položek
        for item in order.items.all():
            if item.product.product_type == "course":
                CourseAccess.objects.update_or_create(
                    user=user,
                    course=item.product.course,
                    defaults={
                        "plan": item.plan,
                        "is_active": True,
                    },
                )

    return HttpResponse(status=200)


def remove_from_cart(request, item_id):
    cart = get_or_create_cart(request)

    try:
        item = cart.items.get(id=item_id)
        item.delete()
    except OrderItem.DoesNotExist:
        pass

    return redirect("payments:cart_detail")

def course_list(request):
    courses = Product.objects.filter(
        product_type="course",
        is_active=True
    ).select_related("course")

    return render(request, "payments/course_list.html", {
        "courses": courses
    })

def course_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("course"),
        slug=slug,
        product_type="course",
        is_active=True
    )

    plans = CoursePlan.objects.filter(
        course=product.course,
        is_active=True
    )

    return render(request, "payments/course_detail.html", {
        "product": product,
        "plans": plans
    })

def physical_list(request):
    products = Product.objects.filter(
        product_type="physical",
        is_active=True
    )

    return render(request, "payments/physical_list.html", {
        "products": products
    })

def physical_detail(request, slug):
    product = get_object_or_404(
        Product,
        slug=slug,
        product_type="physical",
        is_active=True
    )

    return render(request, "payments/physical_detail.html", {
        "product": product
    })
