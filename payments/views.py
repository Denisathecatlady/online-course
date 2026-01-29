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

from courses.models import Course
from .models import CoursePlan, Order, CourseAccess
from payments.services.invoice import generate_invoice_pdf, assign_invoice_number

# testy
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# STRIPE
# ---------------------------------------------------------------------

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "").strip()


# ---------------------------------------------------------------------
# CHECKOUT – FORMULÁŘ + ODESLÁNÍ NA STRIPE
# ---------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def checkout(request, plan_code):

    try:
        # ----------------------------
        # ZÁKLADNÍ KONTROLY
        # ----------------------------
        if not stripe.api_key:
            return HttpResponseBadRequest("Chybí STRIPE_SECRET_KEY.")

        plan = get_object_or_404(CoursePlan, code=plan_code, is_active=True)
        course = Course.objects.first()
        if not course:
            return HttpResponseBadRequest("Kurz neexistuje.")

        # ----------------------------
        # GET – formulář
        # ----------------------------
        if request.method == "GET":
            return render(
                request,
                "payments/checkout_form.html",
                {
                    "plan": plan,
                    "course": course,
                },
            )

        # ----------------------------
        # POST – data z formuláře
        # ----------------------------
        buyer_email = request.POST.get("email", "").strip()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()

        street = request.POST.get("street", "").strip()
        city = request.POST.get("city", "").strip()
        zip_code = request.POST.get("zip_code", "").strip()
        country = request.POST.get("country", "CZ").strip()

        invoice_name = request.POST.get("invoice_name", "").strip()
        invoice_street = request.POST.get("invoice_street", "").strip()
        invoice_city = request.POST.get("invoice_city", "").strip()
        invoice_zip = request.POST.get("invoice_zip", "").strip()
        invoice_country = request.POST.get("invoice_country", country).strip()

        # ----------------------------
        # POVINNÝ SOUHLAS S PODMÍNKAMI
        # ----------------------------
        
        if not request.POST.get("terms"):
            return HttpResponseBadRequest(
                "Musíš souhlasit s obchodními podmínkami."
            )

        wants_newsletter = bool(request.POST.get("newsletter"))


        if not buyer_email or not first_name or not last_name:
            return HttpResponseBadRequest("Vyplň e-mail, jméno a příjmení.")

        # ----------------------------
        # OBJEDNÁVKA (PENDING)
        # ----------------------------
        order = Order.objects.create(
            user=None,
            course=course,
            plan=plan,
            buyer_email=buyer_email,
            first_name=first_name,
            last_name=last_name,
            street=street,
            city=city,
            zip_code=zip_code,
            country=country,
            invoice_name=invoice_name or f"{first_name} {last_name}",
            invoice_street=invoice_street or street,
            invoice_city=invoice_city or city,
            invoice_zip=invoice_zip or zip_code,
            invoice_country=invoice_country,
            status=Order.Status.PENDING,
        )

        # ----------------------------
        # STRIPE SESSION
        # ----------------------------
        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=buyer_email,
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": "czk",
                        "unit_amount": int(plan.price_czk * 100),
                        "product_data": {
                            "name": plan.name,
                            "description": "Přístup k online kurzu",
                        },
                    },
                }
            ],
            success_url=request.build_absolute_uri("/payments/success/"),
            cancel_url=request.build_absolute_uri("/payments/cancel/"),
            metadata={"order_id": str(order.id)},
        )

        order.stripe_checkout_session_id = session.id
        order.save(update_fields=["stripe_checkout_session_id"])

        return redirect(session.url)

    except Exception:
        # 🔥 TADY SE KONEČNĚ VYPÍŠE CHYBA 🔥
        logger.exception("🔥 CHECKOUT ERROR 🔥")
        return HttpResponse(
            "Interní chyba serveru – chyba byla zalogována.",
            status=500
        )


# ---------------------------------------------------------------------
# SUCCESS / CANCEL
# ---------------------------------------------------------------------

@require_GET
def success(request):
    return render(request, "payments/success.html")


@require_GET
def cancel(request):
    return render(request, "payments/cancel.html")


# ---------------------------------------------------------------------
# STRIPE WEBHOOK
# ---------------------------------------------------------------------

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
            order = Order.objects.select_related("course", "plan").get(id=order_id)
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

        CourseAccess.objects.update_or_create(
            user=user,
            course=order.course,
            defaults={
                "plan": order.plan,
                "is_active": True,
            },
        )

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_url = request.build_absolute_uri(
            reverse(
                "password_reset_confirm",
                kwargs={"uidb64": uid, "token": token}
            )
        )

        email = EmailMessage(
            subject="Přístup ke kurzu a faktura",
            body=f"""Dobrý den pan/paní {order.last_name},

            děkujeme za objednávku online kurzu.

            Kurz: {order.course.title}
            Varianta: {order.plan.name}

            Pro nastavení přístupu si prosím nastavte heslo zde:
            {reset_url}

            V příloze tohoto e-mailu najdete fakturu č. {order.invoice_number}.

            Po nastavení hesla se můžete ihned přihlásit a začít studovat.
            """
            + (
                """\nPokud jste si zakoupili variantu Premium, napište nám prosím na e-mail info@calmdog.cz.
            Do zprávy uveďte, že jste si zakoupili Premium verzi kurzu – co nejdříve vám zašleme další informace.\n"""
                if order.plan.name.lower() == "premium"
                else ""
            )
            + """
            Děkujeme
            CalmDog
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.buyer_email],
        )

        if order.invoice_pdf:
            email.attach_file(order.invoice_pdf.path)

        email.send()

    return HttpResponse(status=200)


