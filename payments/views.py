import os
import stripe
import logging
from decimal import Decimal, ROUND_HALF_UP
from payments.services.packeta import create_packet, get_packet_label_pdf, PacketaError
from django.utils import timezone

from django.conf import settings
from django.core.mail import EmailMessage
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.db import transaction

from shop.models import Product, ProductVariant
from courses.models import CoursePlan
from courses.models import Course
from .models import Order, OrderItem, CourseAccess
from .services.cart import get_or_create_cart
from payments.services.invoice import generate_invoice_pdf, assign_invoice_number


logger = logging.getLogger(__name__)

BUNDLE_DISCOUNT_RATE = Decimal("0.10")


PUBLIC_COURSE_IMAGE_PATHS = {
    "konejsive-signaly-v-praxi": "img/courses/psi-rec-konejsive-signaly-agrese-stekani.png",
    "netahani-na-voditku": "img/courses/kurz_netahani_na_voditku.png",
}


def get_public_course_image_url(course):
    image_path = PUBLIC_COURSE_IMAGE_PATHS.get(course.slug)
    if image_path:
        return static(image_path)
    if course.image:
        return course.image.url
    return static("img/shared/hero-dog.jpg")


def get_course_listing_image_url(course, index):
    image_path = f"img/courses/online_kurz_{index}.png"
    static_file = settings.BASE_DIR / "courses" / "static" / image_path
    if static_file.exists():
        return static(image_path)
    return get_public_course_image_url(course)


def _format_czech_count(value, singular, paucal, plural):
    if value % 100 in {11, 12, 13, 14}:
        form = plural
    else:
        last_digit = value % 10
        if last_digit == 1:
            form = singular
        elif last_digit in {2, 3, 4}:
            form = paucal
        else:
            form = plural
    return f"{value} {form}"


COURSE_MARKETING_CONTENT = {
    "konejsive-signaly-v-praxi": {
        "hero_lead": (
            "Jak nahlížet na konejšivé signály v celkových souvislostech, "
            "správně je interpretovat a adekvátně na ně reagovat."
        ),
        "hero_support": (
            "Kurz je zaměřený na čtení signálů, prevenci konfliktů a budování "
            "zdravého vztahu se psem."
        ),
        "learn_items": [
            "Rozlišit pozdrav, zdvořilou komunikaci od signálů zastavujících konflikt",
            "Vyhodnotit souvislosti s přesměrovaným chováním, stresem a agresí",
            "Umět signály využít v tréninku reaktivních a bázlivých psů",
            "Vyvarovat se chybných interpretací konejšivých signálů",
            "Umět se psem komunikovat v běžném životě",
            "Lépe reagovat na náročné situace s klidem a kontextem",
        ],
        "curriculum": [
            {
                "order": "1",
                "title": "Úvod do konejšivých signálů",
                "meta": "Význam signálů, jejich síla a kontext, ve kterém je psi používají.",
            },
            {
                "order": "2",
                "title": "Konejšivé signály v širších souvislostech",
                "meta": "Propojení se stresem, emocemi a přesměrovaným chováním.",
            },
            {
                "order": "3",
                "title": "Komentované videoukázky z praxe",
                "meta": "Interpretace několika signálů v reálných situacích krok po kroku.",
            },
            {
                "order": "4",
                "title": "Použití v běžném životě i v tréninku",
                "meta": "Jak na signály reagovat a kdy je můžeme využít i my lidé.",
            },
        ],
        "includes": [
            {
                "icon": "▶",
                "title": "Video lekce",
                "text": "4 moduly s výkladem a komentovanými videoukázkami.",
            },
            {
                "icon": "↓",
                "title": "Ke stažení",
                "text": "Podpůrné materiály a návazné podklady ke studiu.",
            },
            {
                "icon": "◎",
                "title": "Certifikace",
                "text": "Premium varianta vede po splnění podmínek k certifikátu.",
            },
            {
                "icon": "◌",
                "title": "Přístup",
                "text": "180 dní od nákupu, s možností vracet se k obsahu vlastním tempem.",
            },
            {
                "icon": "↗",
                "title": "Podpora",
                "text": "Ve variantě Premium navíc online setkání a mentoring.",
            },
        ],
        "about_paragraphs": [
            (
                "Kurz je rozdělen do 4 modulů. V úvodu jsou představeny jednotlivé "
                "konejšivé signály a podrobně vysvětlen jejich význam, síla a vždy i "
                "kontext, ve kterém je psi používají."
            ),
            (
                "V dalších modulech jsou konejšivé signály zasazeny do širších "
                "souvislostí, propojeny s přesměrovaným chováním a se signály stresu. "
                "Výuka je doplněna o praktické videoukázky, které pomáhají porozumění "
                "i správné interpretaci signálů v reálných situacích."
            ),
            (
                "Každý signál je interpretován na několika komentovaných videích v "
                "celém kontextu situace. U každého signálu je vysvětleno, zda je možné "
                "ho využít člověkem a jak, nebo jak reagovat na ty, které my lidé "
                "napodobit nemůžeme."
            ),
        ],
        "audience_items": [
            "Pro ty, kteří chtějí rozumět psí komunikaci",
            "Pro ty, kteří chtějí umět komunikovat se svým psem",
            "Pro ty, kteří chtějí řešit problémové chování psa",
            "Pro ty, kteří chtějí žít se svým psem v souladu",
        ],
        "certification": {
            "eyebrow": "CALMING SIGNALS SPECIALIST",
            "title": "Certifikace",
            "subtitle": "pod vedením Turid Rugaas",
            "note": "100% etický přístup",
        },
    }
}


PLAN_MARKETING_CONTENT = {
    "standard": {
        "eyebrow": "Samostudium",
        "subtitle": (
            "Jedná se o samostudium bez opory lektora. Učební materiály jsou "
            "zpracovány tak, aby vedly k jistější interpretaci signálů i jejich "
            "využití v běžném životě."
        ),
        "highlights": [
            "Správná interpretace konejšivých signálů v celkovém kontextu",
            "Schopnost vyhodnotit závažnost situace a správně reagovat",
            "Použití principů v běžném soužití i v tréninku reaktivních a bázlivých psů",
        ],
        "footnote": (
            "Přístup ke všem materiálům kurzu je po dobu 6 měsíců. "
            "Tato varianta nevede k získání certifikátu."
        ),
    },
    "premium": {
        "eyebrow": "Mentoring a certifikace",
        "subtitle": (
            "Kompletní vzdělávání pro ty, kteří chtějí jít do hloubky a získat "
            "nejen znalosti, ale i podporu lektora."
        ),
        "highlights": [
            "5x online setkání pro rozbor videí a konzultace úkolů",
            "Podpůrná FB skupina a malé pracovní skupiny",
            "Možnost získání certifikátu po úspěšném vypracování všech úkolů",
        ],
        "footnote": (
            "Ideální volba pro ty, kteří chtějí mít jistotu, že konejšivým "
            "signálům opravdu rozumí a umí je správně aplikovat v praxi."
        ),
    },
}


def build_course_marketing_content(course, plans):
    content = COURSE_MARKETING_CONTENT.get(course.slug)
    if not content:
        return None

    access_days = min((plan.access_duration_days for plan in plans), default=180)
    module_count = course.modules.count()
    plan_count = len(plans)

    return {
        **content,
        "metrics": [
            {
                "value": f"{module_count} moduly",
                "label": "strukturovaný obsah a jasný postup",
            },
            {
                "value": f"{plan_count} varianty",
                "label": "samostudium nebo mentoring podle toho, co potřebujete",
            },
            {
                "value": f"{access_days} dní",
                "label": "přístup ke kurzu a možnost vracet se k obsahu",
            },
        ],
    }


def build_plan_cards(plans):
    cards = []

    for plan in plans:
        content = PLAN_MARKETING_CONTENT.get(
            (plan.code or plan.name or "").strip().lower(),
            {
                "eyebrow": "Online kurz",
                "subtitle": "Praktický online obsah zaměřený na porozumění, kontext a přenos do běžného života.",
                "highlights": [
                    "Přístup ke kompletnímu obsahu kurzu",
                    "Studium vlastním tempem",
                    "Praktické ukázky a etický přístup",
                ],
                "footnote": "Varianta kurzu s přístupem ke kompletním materiálům.",
            },
        )
        cards.append({
            "plan": plan,
            **content,
        })

    return cards


def get_stripe_secret_key():
    return settings.STRIPE_SECRET_KEY.strip()


def get_stripe_webhook_secret():
    return settings.STRIPE_WEBHOOK_SECRET.strip()


def build_site_url(path):
    base_url = settings.SITE_URL.rstrip("/")
    return f"{base_url}{path}"


def get_bundle_item_price(price):
    return (price * (Decimal("1.00") - BUNDLE_DISCOUNT_RATE)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def add_product_variant_to_order(cart, variant, quantity, price_at_purchase=None):
    if variant.stock <= 0:
        raise ValueError("Produkt není skladem.")

    if quantity > variant.stock:
        raise ValueError("Není dostatek kusů skladem.")

    item_price = price_at_purchase if price_at_purchase is not None else variant.price

    order_item, created = OrderItem.objects.get_or_create(
        order=cart,
        product_variant=variant,
        defaults={
            "quantity": quantity,
            "price_at_purchase": item_price,
        }
    )

    if not created:
        new_quantity = order_item.quantity + quantity

        if new_quantity > variant.stock:
            raise ValueError("Překročen dostupný sklad.")

        current_total = order_item.price_at_purchase * order_item.quantity
        added_total = item_price * quantity
        order_item.quantity = new_quantity
        order_item.price_at_purchase = ((current_total + added_total) / new_quantity).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        order_item.save(update_fields=["quantity", "price_at_purchase"])


# =====================================================
# KOŠÍK – ONLINE KURZ
# =====================================================

@require_POST
def add_course_to_cart(request, plan_id):

    plan = get_object_or_404(
        CoursePlan,
        id=plan_id,
        is_active=True
    )

    cart = get_or_create_cart(request)

    OrderItem.objects.get_or_create(
        order=cart,
        course_plan=plan,
        defaults={
            "quantity": 1,
            "price_at_purchase": plan.price
        }
    )

    return redirect("payments:cart_detail")

# =====================================================
# KOŠÍK – FYZICKÝ PRODUKT (VODÍTKO)
# =====================================================
@require_POST
def add_variant_to_cart(request, variant_id):

    variant = get_object_or_404(
        ProductVariant,
        id=variant_id,
        is_active=True
    )

    cart = get_or_create_cart(request)

    quantity = int(request.POST.get("quantity", 1))
    try:
        add_product_variant_to_order(cart, variant, quantity)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    return redirect("payments:cart_detail")


@require_POST
def add_bundle_to_cart(request, variant_id):
    primary_variant = get_object_or_404(
        ProductVariant,
        id=variant_id,
        is_active=True,
    )

    bundle_variant_id = request.POST.get("bundle_variant_id")
    if not bundle_variant_id:
        return HttpResponseBadRequest("Chybí doplňková varianta pro bundle.")

    bundle_variant = get_object_or_404(
        ProductVariant,
        id=bundle_variant_id,
        is_active=True,
    )

    if primary_variant.product.slug != "voditko-bez-ocka":
        return HttpResponseBadRequest("Bundle lze vytvořit jen k vodítku bez očka.")

    if bundle_variant.product.slug != "samostatne-ocko":
        return HttpResponseBadRequest("Neplatná doplňková varianta.")

    if primary_variant.color_id != bundle_variant.color_id:
        return HttpResponseBadRequest("Bundle musí mít shodnou barvu obou částí.")

    quantity = int(request.POST.get("quantity", 1))
    cart = get_or_create_cart(request)

    try:
        with transaction.atomic():
            add_product_variant_to_order(
                cart,
                primary_variant,
                quantity,
                price_at_purchase=get_bundle_item_price(primary_variant.price),
            )
            add_product_variant_to_order(
                cart,
                bundle_variant,
                quantity,
                price_at_purchase=get_bundle_item_price(bundle_variant.price),
            )
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))

    return redirect("payments:cart_detail")

# =====================================================
# DETAIL KOŠÍKU
# =====================================================

def cart_detail(request):
    cart = get_or_create_cart(request)

    cart = Order.objects.prefetch_related(
        "items__product_variant__product",
        "items__course_plan__course"
    ).get(id=cart.id)

    has_physical_products = cart.contains_physical_product()

    return render(request, "payments/cart.html", {
        "order": cart,
        "items": cart.items.all(),
        "has_physical_products": has_physical_products,
    })

# =====================================================
# CHECKOUT
# =====================================================

@require_http_methods(["GET", "POST"])
def checkout(request):
    cart = get_or_create_cart(request)

    cart = (
        Order.objects
        .prefetch_related(
            "items__product_variant__product",
            "items__course_plan__course"
        )
        .get(id=cart.id)
    )

    if not cart.items.exists():
        return HttpResponseBadRequest("Košík je prázdný.")

    has_physical_products = cart.contains_physical_product()
    is_packeta_delivery = cart.shipping_method == Order.ShippingMethod.ZASILKOVNA

    if has_physical_products and not cart.shipping_method:
        return redirect("payments:shipping")

    if request.method == "GET":
        return render(request, "payments/checkout_form.html", {
            "cart": cart,
            "items": cart.items.all(),
            "has_physical_products": has_physical_products,
            "is_packeta_delivery": is_packeta_delivery,
        })

    stripe_secret_key = get_stripe_secret_key()

    if not stripe_secret_key:
        return HttpResponseBadRequest("Chybí STRIPE_SECRET_KEY.")

    if not stripe_secret_key.startswith("sk_"):
        logger.error("Invalid STRIPE_SECRET_KEY configured. Expected secret key starting with 'sk_'.")
        return HttpResponseBadRequest("Neplatná konfigurace Stripe.")

    stripe.api_key = stripe_secret_key

    # ------------------------------
    # ULOŽENÍ ÚDAJŮ
    # ------------------------------

    cart.buyer_email = request.POST.get("email", "").strip()
    cart.first_name = request.POST.get("first_name", "").strip()
    cart.last_name = request.POST.get("last_name", "").strip()
    cart.phone = request.POST.get("phone", "").strip()
    cart.street = request.POST.get("street", "").strip()
    cart.city = request.POST.get("city", "").strip()
    cart.zip_code = request.POST.get("zip_code", "").strip()
    cart.country = request.POST.get("country", "CZ").strip()
    cart.invoice_name = request.POST.get("invoice_name", "").strip()
    cart.invoice_street = request.POST.get("invoice_street", "").strip()
    cart.invoice_city = request.POST.get("invoice_city", "").strip()
    cart.invoice_zip = request.POST.get("invoice_zip", "").strip()
    cart.invoice_country = request.POST.get("invoice_country", "CZ").strip()
    cart.newsletter_opt_in = bool(request.POST.get("newsletter"))
    cart.status = Order.Status.PENDING

    cart.save(update_fields=[
        "buyer_email",
        "first_name",
        "last_name",
        "phone",
        "street",
        "city",
        "zip_code",
        "country",
        "invoice_name",
        "invoice_street",
        "invoice_city",
        "invoice_zip",
        "invoice_country",
        "newsletter_opt_in",
        "status"
    ])

    # Pokud je fyzický produkt a není doprava
    # ------------------------------
    # STRIPE LINE ITEMS
    # ------------------------------

    line_items = []

    for item in cart.items.all():

        if item.course_plan:
            name = item.course_plan.course.title
        elif item.product_variant:
            name = item.product_variant.product.name
        else:
            continue

        line_items.append({
            "quantity": item.quantity,
            "price_data": {
                "currency": "czk",
                "unit_amount": int(item.price_at_purchase * 100),
                "product_data": {"name": name},
            },
        })

    if cart.shipping_price > 0:
        line_items.append({
            "quantity": 1,
            "price_data": {
                "currency": "czk",
                "unit_amount": int(cart.shipping_price * 100),
                "product_data": {
                    "name": f"Doprava – {cart.get_shipping_method_display()}",
                },
            },
        })

    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=cart.buyer_email,
        line_items=line_items,
        success_url=build_site_url("/payments/success/"),
        cancel_url=build_site_url("/payments/cancel/"),
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
    endpoint_secret = get_stripe_webhook_secret()

    stripe_secret_key = get_stripe_secret_key()
    if stripe_secret_key.startswith("sk_"):
        stripe.api_key = stripe_secret_key

    if not endpoint_secret:
        logger.error("Missing STRIPE_WEBHOOK_SECRET.")
        return HttpResponseBadRequest("Missing webhook configuration")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=endpoint_secret,
        )
    except Exception:
        return HttpResponseBadRequest("Invalid webhook")

    if event["type"] != "checkout.session.completed":
        return HttpResponse(status=200)

    session = event["data"]["object"]
    order_id = session.get("metadata", {}).get("order_id")

    if not order_id:
        return HttpResponse(status=200)

    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return HttpResponse(status=200)

    # Pokud už je zaplaceno → nic nedělat
    if order.status == Order.Status.PAID:
        return HttpResponse(status=200)

    # ======================================
    # 1️⃣ ULOŽENÍ ZAPLACENÍ (KRITICKÁ ČÁST)
    # ======================================

    with transaction.atomic():

        order = (
            Order.objects
            .select_for_update()
            .prefetch_related("items__product_variant", "items__course_plan__course")
            .get(id=order_id)
        )

        order.status = Order.Status.PAID
        order.stripe_payment_intent_id = session.get("payment_intent", "")
        order.save(update_fields=["status", "stripe_payment_intent_id"])

        assign_invoice_number(order)

        invoice_file = generate_invoice_pdf(order)
        order.invoice_pdf.save(invoice_file.name, invoice_file)
        order.save(update_fields=["invoice_pdf"])

        # ======================================
        # 2️⃣ ODEČTENÍ SKLADU (POUZE JEDNOU)
        # ======================================

        if not order.stock_reduced:

            for item in order.items.all():

                if item.product_variant:

                    variant = (
                        ProductVariant.objects
                        .select_for_update()
                        .get(id=item.product_variant.id)
                    )

                    if item.quantity > variant.stock:
                        logger.error(
                            f"Insufficient stock for variant {variant.id} "
                            f"in order {order.id}"
                        )
                        continue

                    variant.stock -= item.quantity
                    variant.save(update_fields=["stock"])

            order.stock_reduced = True
            order.save(update_fields=["stock_reduced"])

    # ======================================
    # 3️⃣ VYTVOŘENÍ ZÁSILKY (MIMO TRANSACTION)
    # ======================================

    if (
        order.shipping_method == Order.ShippingMethod.ZASILKOVNA
        and not order.packeta_packet_id
    ):
        try:
            shipment = create_packet(order)

            order.packeta_packet_id = shipment["packet_id"]
            order.packeta_tracking_number = shipment["tracking_number"]
            order.packeta_created_at = timezone.now()

            order.save(update_fields=[
                "packeta_packet_id",
                "packeta_tracking_number",
                "packeta_created_at",
            ])

            # ── stažení štítku jako PDF ─────────────────────
            try:
                label_pdf_bytes = get_packet_label_pdf(order.packeta_packet_id)
                label_filename = f"label_packeta_{order.id}.pdf"
                from django.core.files.base import ContentFile
                order.packeta_label_pdf.save(
                    label_filename,
                    ContentFile(label_pdf_bytes),
                    save=True,
                )
                logger.info(
                    f"[Packeta] Štítek uložen pro objednávku #{order.id}"
                )
            except Exception as label_err:
                logger.error(
                    f"[Packeta] Nepodařilo se stáhnout štítek pro objednávku "
                    f"#{order.id}: {label_err}"
                )

        except PacketaError as e:
            logger.error(
                f"[Packeta] API chyba při vytváření zásilky "
                f"(objednávka #{order.id}): [{e.code}] {e.message}"
            )
        except Exception as e:
            logger.error(
                f"[Packeta] Neočekávaná chyba při vytváření zásilky "
                f"(objednávka #{order.id}): {e}"
            )

    # ======================================
    # 4️⃣ VYTVOŘENÍ / NAPOJENÍ UŽIVATELE
    # ======================================

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

    # ======================================
    # 5️⃣ PŘÍSTUP KE KURZŮM
    # ======================================

    for item in order.items.all():
        if item.course_plan:
            CourseAccess.objects.update_or_create(
                user=user,
                course=item.course_plan.course,
                defaults={
                    "plan": item.course_plan,
                    "is_active": True,
                },
            )

    # ======================================
    # 6️⃣ EMAIL ZÁKAZNÍKOVI
    # ======================================

    _send_order_confirmation_email(order, user, created, request)

    return HttpResponse(status=200)


def _send_order_confirmation_email(order, user, user_was_created, request):
    """
    Pošle zákazníkovi potvrzovací email s fakturou a (pokud je nový uživatel)
    odkazem pro nastavení hesla.
    """
    try:
        # --- odkaz na nastavení hesla (jen nový uživatel) ---
        reset_section = ""
        if user_was_created:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_url = request.build_absolute_uri(
                reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
            )
            reset_section = (
                f"\nPro nastavení hesla a přístup ke kurzu klikněte zde:\n{reset_url}\n"
            )

        # --- sestavení položek ---
        items_text = ""
        for item in order.items.select_related("course_plan__course", "product_variant__product").all():
            if item.course_plan:
                items_text += f"  • Online kurz: {item.course_plan.course.title} – varianta {item.course_plan.name} ({item.price_at_purchase:.0f} Kč)\n"
            elif item.product_variant:
                items_text += f"  • {item.product_variant.product.name} ({item.price_at_purchase:.0f} Kč × {item.quantity} ks)\n"

        if order.shipping_price:
            items_text += f"  • Doprava – {order.get_shipping_method_display()}: {order.shipping_price:.0f} Kč\n"

        body = f"""Dobrý den, {order.first_name} {order.last_name},

děkujeme za Váš nákup v CalmDog!

Přehled objednávky č. {order.id}:
{items_text}
Celkem: {order.total_price:.0f} Kč
{reset_section}
V příloze najdete fakturu č. {order.invoice_number}.

S pozdravem,
CalmDog
info@calmdog.cz
+420 608 163 824
"""

        email = EmailMessage(
            subject=f"CalmDog – potvrzení objednávky č. {order.id}",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.buyer_email],
        )

        # --- faktura v příloze (kompatibilní s R2 i lokálním úložištěm) ---
        if order.invoice_pdf:
            order.invoice_pdf.open("rb")
            email.attach(
                f"faktura_{order.invoice_number}.pdf",
                order.invoice_pdf.read(),
                "application/pdf",
            )
            order.invoice_pdf.close()

        email.send()

    except Exception as e:
        logger.error(f"Failed to send order confirmation email for order {order.id}: {e}")
# =====================================================
# ODEBRÁNÍ Z KOŠÍKU
# =====================================================

def remove_from_cart(request, item_id):
    cart = get_or_create_cart(request)

    try:
        item = cart.items.get(id=item_id)
        item.delete()
    except OrderItem.DoesNotExist:
        pass

    return redirect("payments:cart_detail")


# =====================================================
# LIST + DETAIL KURZŮ
# =====================================================

def course_list(request):
    courses = list(Course.objects.all().prefetch_related("plans", "modules"))

    for index, course in enumerate(courses, start=1):
        active_plans = [plan for plan in course.plans.all() if plan.is_active]
        course.public_image_url = get_public_course_image_url(course)
        course.listing_image_url = get_course_listing_image_url(course, index)
        course.listing_description = (
            course.public_intro
            or course.about_text
            or course.private_intro
            or "Praktický online kurz zaměřený na klidnější soužití se psem."
        )
        course.active_plan_count = len(active_plans)
        course.min_price = min((plan.price for plan in active_plans), default=None)
        course.access_days = min((plan.access_duration_days for plan in active_plans), default=None)
        course.module_count = len(course.modules.all())
        course.meta_access = (
            _format_czech_count(course.access_days, "den", "dny", "dní")
            if course.access_days
            else None
        )
        course.meta_modules = (
            _format_czech_count(course.module_count, "modul", "moduly", "modulů")
            if course.module_count
            else None
        )
        course.meta_variants = (
            _format_czech_count(course.active_plan_count, "varianta", "varianty", "variant")
            if course.active_plan_count
            else None
        )

    return render(request, "payments/course_list.html", {
        "courses": courses
    })

def course_detail(request, slug):
    course = get_object_or_404(
        Course,
        slug=slug
    )

    plans = list(
        course.plans
        .filter(is_active=True)
        .order_by("price", "id")
    )
    featured_plan = plans[0] if plans else None
    course_marketing = build_course_marketing_content(course, plans)
    plan_cards = build_plan_cards(plans)
    course.public_image_url = get_public_course_image_url(course)

    return render(request, "payments/course_detail.html", {
        "course": course,
        "plans": plans,
        "featured_plan": featured_plan,
        "course_marketing": course_marketing,
        "plan_cards": plan_cards,
    })

# =====================================================
# VOLBA DOPRAVY (POKUD JE V KOŠÍKU FYZICKÝ PRODUKT)
# =====================================================
@require_http_methods(["GET", "POST"])
def shipping(request):

    cart = get_or_create_cart(request)
    cart = Order.objects.get(id=cart.id)

    if not cart.contains_physical_product():
        return redirect("payments:contact_details")

    if request.method == "POST":

        method = request.POST.get("shipping_method")
        packeta_point_id = request.POST.get("packeta_point_id", "").strip()
        packeta_point_name = request.POST.get("packeta_point_name", "").strip()

        if method == Order.ShippingMethod.ZASILKOVNA and settings.PACKETA_MODE == "mock":
            packeta_point_id = packeta_point_id or settings.PACKETA_MOCK_POINT_ID
            packeta_point_name = packeta_point_name or settings.PACKETA_MOCK_POINT_NAME

        if method == Order.ShippingMethod.ZASILKOVNA and not packeta_point_id:
            return render(request, "payments/shipping.html", {
                "order": cart,
                "error": "Pro Zásilkovnu vyberte výdejní místo.",
                "selected_method": method,
                "packeta_point_id": packeta_point_id,
                "packeta_point_name": packeta_point_name,
                "packeta_widget_api_key": settings.PACKETA_WIDGET_API_KEY,
                "packeta_mode": settings.PACKETA_MODE,
                "packeta_mock_point_id": settings.PACKETA_MOCK_POINT_ID,
                "packeta_mock_point_name": settings.PACKETA_MOCK_POINT_NAME,
            })

        cart.shipping_method = method

        if method == Order.ShippingMethod.ZASILKOVNA:
            cart.shipping_price = 79
            cart.packeta_point_id = packeta_point_id
            cart.packeta_point_name = packeta_point_name or packeta_point_id
        elif method == Order.ShippingMethod.KURYR:
            cart.shipping_price = 119
            cart.packeta_point_id = None
            cart.packeta_point_name = None
        else:
            cart.shipping_price = 0
            cart.packeta_point_id = None
            cart.packeta_point_name = None

        cart.save(update_fields=[
            "shipping_method",
            "shipping_price",
            "packeta_point_id",
            "packeta_point_name",
        ])

        return redirect("payments:contact_details")

    return render(request, "payments/shipping.html", {
        "order": cart,
        "selected_method": cart.shipping_method,
        "packeta_point_id": cart.packeta_point_id or "",
        "packeta_point_name": cart.packeta_point_name or "",
        "packeta_widget_api_key": settings.PACKETA_WIDGET_API_KEY,
        "packeta_mode": settings.PACKETA_MODE,
        "packeta_mock_point_id": settings.PACKETA_MOCK_POINT_ID,
        "packeta_mock_point_name": settings.PACKETA_MOCK_POINT_NAME,
    })
