"""
Integrační testy: celý nákupní flow pro tři scénáře
====================================================

1. FullLeashPurchaseTests
   Host (nepřihlášený) koupí fyzické vodítko a zvolí Zásilkovnu.
   Flow: přidání → výběr dopravy → checkout → Stripe webhook

2. FullCoursePurchaseTests
   Host koupí online kurz bez fyzické dopravy.
   Flow: přidání → checkout (přeskočí shipping) → Stripe webhook → CourseAccess

3. CombinedLeashAndCoursePurchaseTests
   Host koupí vodítko + kurz dohromady.
   Flow: přidání obou → Zásilkovna → checkout → webhook → sklad + CourseAccess

Mockujeme:
  - stripe.checkout.Session.create
  - stripe.Webhook.construct_event
  - payments.views.generate_invoice_pdf
  - payments.views.assign_invoice_number
  - payments.views.create_packet
  - payments.views.get_packet_label_pdf
  - MEDIA_ROOT → tmp adresář (vyhne se zápisům na disk)
"""

import io
import json
import tempfile
from contextlib import ExitStack
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from courses.models import Course, CoursePlan
from payments.models import CourseAccess, Order, OrderItem
from shop.models import Color, Product, ProductVariant

User = get_user_model()


# ---------------------------------------------------------------------------
# Sdílené konstanty a tovární funkce
# ---------------------------------------------------------------------------

_STRIPE_KEY = "sk_test_fake_integration_test_key"
_WEBHOOK_SECRET = "whsec_fakewebhooksecretfortests"
_TMP_MEDIA = tempfile.mkdtemp(prefix="calmdogtest_media_")

OVERRIDE = dict(
    STRIPE_SECRET_KEY=_STRIPE_KEY,
    STRIPE_WEBHOOK_SECRET=_WEBHOOK_SECRET,
    PACKETA_MODE="mock",
    MEDIA_ROOT=_TMP_MEDIA,
)


def _fake_stripe_session(session_id: str = "cs_test_abc123") -> MagicMock:
    s = MagicMock()
    s.id = session_id
    s.url = f"https://checkout.stripe.com/pay/{session_id}"
    return s


def _webhook_event(order_id: int, payment_intent: str = "pi_test_fake") -> dict:
    """Fake Stripe `checkout.session.completed` event."""
    return {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_abc123",
                "payment_intent": payment_intent,
                "customer_email": "buyer@example.com",
                "metadata": {"order_id": str(order_id)},
            }
        },
    }


def _fake_invoice() -> io.BytesIO:
    """Minimální BytesIO, který lze uložit jako FileField."""
    buf = io.BytesIO(b"%PDF-1.4 fake invoice for tests")
    buf.name = "faktura_test.pdf"
    return buf


def _fire_webhook(client, order_id: int):
    """
    Odešle POST /stripe-webhook/ s fake eventem.
    Automaticky mockuje všechny externí závislosti.
    Vrací (response, mock_create_packet).
    """
    event = _webhook_event(order_id)
    packet_result = {
        "packet_id": f"ZMOCK{order_id:08d}",
        "tracking_number": f"ZP{order_id:010d}CZ",
    }

    with ExitStack() as stack:
        stack.enter_context(
            patch("payments.views.stripe.Webhook.construct_event", return_value=event)
        )
        stack.enter_context(
            patch("payments.views.generate_invoice_pdf", return_value=_fake_invoice())
        )
        stack.enter_context(patch("payments.views.assign_invoice_number"))
        mock_packet = stack.enter_context(
            patch("payments.views.create_packet", return_value=packet_result)
        )
        stack.enter_context(
            patch("payments.views.get_packet_label_pdf", return_value=b"%PDF-fake-label")
        )

        response = client.post(
            reverse("payments:stripe_webhook"),
            data=json.dumps(event),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=fake,v1=fakesig",
        )

    return response, mock_packet


# ---------------------------------------------------------------------------
# Shared POST data pro checkout formulář
# ---------------------------------------------------------------------------

def _checkout_data(email: str, first_name: str, last_name: str) -> dict:
    return {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "phone": "777000001",
        "street": "Testovací 1",
        "city": "Praha",
        "zip_code": "11000",
        "country": "CZ",
        "invoice_name": f"{first_name} {last_name}",
        "invoice_street": "Testovací 1",
        "invoice_city": "Praha",
        "invoice_zip": "11000",
        "invoice_country": "CZ",
    }


# ===========================================================================
# 1.  Plný nákup fyzického vodítka + Zásilkovna
# ===========================================================================

@override_settings(**OVERRIDE)
class FullLeashPurchaseTests(TestCase):
    """
    Scénář:
    Host si koupí vodítko bez očka (7 m, Šedá, cena 1 490 Kč)
    a zvolí dopravu Zásilkovnou (99 Kč).

    Testujeme každý krok flow samostatně i finální stav po webhoku.
    """

    def setUp(self):
        self.product = Product.objects.create(
            name="Vodítko bez očka",
            slug="voditko-bez-ocka",
            is_active=True,
        )
        self.color = Color.objects.create(name="Šedá", hex_code="#888888")
        self.variant = ProductVariant.objects.create(
            product=self.product,
            color=self.color,
            length="7",
            type="no_loop",
            price="1490.00",
            stock=3,
            is_active=True,
        )

    # ── privátní helpery ─────────────────────────────────────────────────────

    def _add_to_cart(self):
        return self.client.post(
            reverse("payments:add_variant_to_cart", args=[self.variant.id])
        )

    def _select_zasilkovna(self):
        return self.client.post(
            reverse("payments:shipping"),
            {
                "shipping_method": Order.ShippingMethod.ZASILKOVNA,
                "packeta_point_id": "12345",
                "packeta_point_name": "Z-BOX Praha 1 - Vodičkova",
            },
        )

    def _post_checkout(self):
        data = _checkout_data("zakaznik@example.com", "Jana", "Dvořáková")
        return self.client.post(reverse("payments:contact_details"), data)

    # ── testy ────────────────────────────────────────────────────────────────

    def test_01_add_variant_creates_session_cart(self):
        """Přidání varianty vytvoří košík a uloží jeho ID do session."""
        response = self._add_to_cart()

        self.assertRedirects(response, reverse("payments:cart_detail"))
        self.assertIn("cart_id", self.client.session)

        cart = Order.objects.get(status=Order.Status.CART)
        self.assertEqual(cart.items.count(), 1)
        item = cart.items.get()
        self.assertEqual(item.product_variant, self.variant)
        self.assertEqual(str(item.price_at_purchase), "1490.00")
        self.assertIsNone(cart.user)  # host, bez účtu

    def test_02_checkout_redirects_to_shipping_without_selection(self):
        """GET /checkout/ přesměruje na /shipping/, pokud fyzická doprava není zvolena."""
        self._add_to_cart()

        response = self.client.get(reverse("payments:contact_details"))

        self.assertRedirects(response, reverse("payments:shipping"))

    def test_03_zasilkovna_saves_pickup_point_and_price(self):
        """POST /shipping/ uloží výdejní místo Zásilkovny a cenu 99 Kč."""
        self._add_to_cart()

        response = self._select_zasilkovna()

        self.assertRedirects(response, reverse("payments:contact_details"))
        cart = Order.objects.get(status=Order.Status.CART)
        self.assertEqual(cart.shipping_method, Order.ShippingMethod.ZASILKOVNA)
        self.assertEqual(str(cart.shipping_price), "99.00")
        self.assertEqual(cart.packeta_point_id, "12345")
        self.assertEqual(cart.packeta_point_name, "Z-BOX Praha 1 - Vodičkova")

    def test_04_checkout_post_creates_stripe_session_and_redirects(self):
        """POST /checkout/ zavolá Stripe a přesměruje zákazníka na platební bránu."""
        self._add_to_cart()
        self._select_zasilkovna()

        fake_session = _fake_stripe_session()
        with patch("payments.views.stripe.checkout.Session.create", return_value=fake_session):
            response = self._post_checkout()

        self.assertRedirects(response, fake_session.url, fetch_redirect_response=False)

        order = Order.objects.get(stripe_checkout_session_id="cs_test_abc123")
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.buyer_email, "zakaznik@example.com")
        self.assertEqual(order.first_name, "Jana")
        self.assertEqual(order.last_name, "Dvořáková")

    def test_05_webhook_completes_full_purchase(self):
        """
        Stripe webhook checkout.session.completed dokončí nákup:
        - objednávka přejde do stavu PAID
        - sklad vodítka se sníží o 1
        - zásilka Packeta se vytvoří
        - zákazník dostane nový uživatelský účet
        - odejde potvrzovací email
        """
        self._add_to_cart()
        self._select_zasilkovna()
        fake_session = _fake_stripe_session()
        with patch("payments.views.stripe.checkout.Session.create", return_value=fake_session):
            self._post_checkout()

        order = Order.objects.get(stripe_checkout_session_id="cs_test_abc123")

        response, mock_packet = _fire_webhook(self.client, order.id)

        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertTrue(order.stock_reduced)
        self.assertEqual(order.stripe_payment_intent_id, "pi_test_fake")
        self.assertEqual(order.packeta_packet_id, f"ZMOCK{order.id:08d}")
        self.assertEqual(order.packeta_tracking_number, f"ZP{order.id:010d}CZ")

        # Sklad se snížil o 1 (bylo 3 → 2)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 2)

        # Byl vytvořen nový uživatel (buyer_email)
        user = User.objects.get(email="zakaznik@example.com")
        self.assertEqual(user.first_name, "Jana")
        self.assertEqual(user.last_name, "Dvořáková")

        # Packeta API bylo zavoláno
        mock_packet.assert_called_once()

        # Potvrzovací email zákazníkovi + interní upozornění na info@calmdog.cz
        self.assertEqual(len(mail.outbox), 2)
        recipients = [email.to[0] for email in mail.outbox]
        self.assertIn("zakaznik@example.com", recipients)
        self.assertIn("info@calmdog.cz", recipients)

    def test_06_webhook_is_idempotent_for_already_paid_order(self):
        """
        Opakovaný webhook (Stripe retry) na objednávku ve stavu PAID
        nesmí znovu snižovat sklad ani volat Packeta.
        """
        # Připravíme objednávku rovnou ve stavu PAID
        order = Order.objects.create(
            status=Order.Status.PAID,
            buyer_email="zakaznik@example.com",
            first_name="Jana",
            last_name="Dvořáková",
            shipping_method=Order.ShippingMethod.ZASILKOVNA,
            shipping_price="79.00",
            packeta_point_id="12345",
            packeta_point_name="Z-BOX Praha 1",
            packeta_packet_id="ZMOCK_ALREADY",
            stock_reduced=True,
        )
        OrderItem.objects.create(
            order=order,
            product_variant=self.variant,
            quantity=1,
            price_at_purchase="1490.00",
        )
        stock_before = self.variant.stock

        response, mock_packet = _fire_webhook(self.client, order.id)

        self.assertEqual(response.status_code, 200)
        # Sklad se nezměnil
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, stock_before)
        # Packeta se nevolala
        mock_packet.assert_not_called()


# ===========================================================================
# 2.  Plný nákup online kurzu (bez fyzické dopravy)
# ===========================================================================

@override_settings(**OVERRIDE)
class FullCoursePurchaseTests(TestCase):
    """
    Scénář:
    Host si koupí online kurz (2 490 Kč, 180 dní přístupu).
    Neprochází výběrem dopravy.
    Webhook udělí CourseAccess a vytvoří uživatele.
    """

    def setUp(self):
        self.course = Course.objects.create(
            title="Konejšivé signály v praxi",
            slug="konejsive-signaly-v-praxi",
            is_active=True,
        )
        self.plan = CoursePlan.objects.create(
            course=self.course,
            name="Standard",
            code="standard",
            price="2490.00",
            access_duration_days=180,
            is_active=True,
        )

    # ── privátní helpery ─────────────────────────────────────────────────────

    def _add_course(self):
        return self.client.post(
            reverse("payments:add_course_to_cart", args=[self.plan.id])
        )

    def _post_checkout(self):
        data = _checkout_data("student@example.com", "Petra", "Kratochvílová")
        return self.client.post(reverse("payments:contact_details"), data)

    # ── testy ────────────────────────────────────────────────────────────────

    def test_01_add_course_creates_digital_only_cart(self):
        """Přidání kurzu vytvoří košík bez fyzických produktů."""
        response = self._add_course()

        self.assertRedirects(response, reverse("payments:cart_detail"))
        cart = Order.objects.get(status=Order.Status.CART)
        self.assertFalse(cart.contains_physical_product())
        item = cart.items.get()
        self.assertEqual(item.course_plan, self.plan)
        self.assertEqual(str(item.price_at_purchase), "2490.00")

    def test_02_checkout_skips_shipping_for_digital_only_cart(self):
        """GET /checkout/ rovnou zobrazí formulář (košík neobsahuje fyzické zboží)."""
        self._add_course()

        response = self.client.get(reverse("payments:contact_details"))

        # Nesmí přesměrovat na /shipping/
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.get("Location", ""), reverse("payments:shipping"))

    def test_03_checkout_post_creates_stripe_session(self):
        """POST /checkout/ přesměruje na Stripe checkout."""
        self._add_course()
        fake_session = _fake_stripe_session()
        with patch("payments.views.stripe.checkout.Session.create", return_value=fake_session):
            response = self._post_checkout()

        self.assertRedirects(response, fake_session.url, fetch_redirect_response=False)
        order = Order.objects.get(stripe_checkout_session_id="cs_test_abc123")
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(order.buyer_email, "student@example.com")

    def test_04_webhook_grants_course_access_to_new_user(self):
        """
        Webhook vytvoří uživatele a udělí CourseAccess ke kurzu.
        Packeta se NEZAVOLÁ (čistě digitální objednávka).
        """
        self._add_course()
        fake_session = _fake_stripe_session()
        with patch("payments.views.stripe.checkout.Session.create", return_value=fake_session):
            self._post_checkout()

        order = Order.objects.get(stripe_checkout_session_id="cs_test_abc123")

        response, mock_packet = _fire_webhook(self.client, order.id)

        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)

        # Nový uživatel vytvořen
        user = User.objects.get(email="student@example.com")
        self.assertEqual(user.first_name, "Petra")
        self.assertEqual(user.last_name, "Kratochvílová")

        # CourseAccess udělen
        access = CourseAccess.objects.get(user=user, course=self.course)
        self.assertTrue(access.is_active)
        self.assertEqual(access.plan, self.plan)
        self.assertIsNotNone(access.expires_at)  # auto-nastaveno z access_duration_days

        # Packeta se nevolala (není fyzický produkt)
        mock_packet.assert_not_called()

        # Email odeslán
        self.assertEqual(len(mail.outbox), 1)

    def test_05_webhook_grants_access_to_existing_user(self):
        """
        Pokud zákazník má existující účet (stejný email), webhook ho
        nezmnoží – stále existuje jen jeden uživatel a CourseAccess je udělena.
        """
        existing = User.objects.create_user(
            username="student@example.com",
            email="student@example.com",
            first_name="Petra",
        )

        self._add_course()
        fake_session = _fake_stripe_session()
        with patch("payments.views.stripe.checkout.Session.create", return_value=fake_session):
            self._post_checkout()

        order = Order.objects.get(stripe_checkout_session_id="cs_test_abc123")
        _fire_webhook(self.client, order.id)

        # Stále jen jeden uživatel s tímto emailem
        self.assertEqual(User.objects.filter(email="student@example.com").count(), 1)

        # CourseAccess existuje a patří existujícímu uživateli
        access = CourseAccess.objects.get(user=existing, course=self.course)
        self.assertTrue(access.is_active)

    def test_06_webhook_does_not_duplicate_course_access_on_retry(self):
        """
        Opakovaný webhook (update_or_create) nesmí vytvořit druhý záznam CourseAccess.
        """
        self._add_course()
        fake_session = _fake_stripe_session()
        with patch("payments.views.stripe.checkout.Session.create", return_value=fake_session):
            self._post_checkout()

        order = Order.objects.get(stripe_checkout_session_id="cs_test_abc123")
        _fire_webhook(self.client, order.id)
        _fire_webhook(self.client, order.id)  # retry

        user = User.objects.get(email="student@example.com")
        count = CourseAccess.objects.filter(user=user, course=self.course).count()
        self.assertEqual(count, 1)


# ===========================================================================
# 3.  Kombinovaný nákup: fyzické vodítko + online kurz + Zásilkovna
# ===========================================================================

@override_settings(**OVERRIDE)
class CombinedLeashAndCoursePurchaseTests(TestCase):
    """
    Scénář:
    Host přidá do košíku vodítko (1 590 Kč, 10 m, Pastelově růžová)
    i online kurz (3 490 Kč, 365 dní).
    Zvolí Zásilkovnu (99 Kč).
    Webhook musí:
      - snížit sklad vodítka o 1
      - udělit CourseAccess ke kurzu
      - vytvořit zásilku Packeta
      - odeslat email
    """

    def setUp(self):
        # Fyzický produkt
        self.product = Product.objects.create(
            name="Vodítko bez očka",
            slug="voditko-bez-ocka",
            is_active=True,
        )
        self.color = Color.objects.create(name="Pastelově růžová", hex_code="#f7c5c5")
        self.variant = ProductVariant.objects.create(
            product=self.product,
            color=self.color,
            length="10",
            type="no_loop",
            price="1590.00",
            stock=4,
            is_active=True,
        )
        # Online kurz
        self.course = Course.objects.create(
            title="Netahání na vodítku",
            slug="netahani-na-voditku",
            is_active=True,
        )
        self.plan = CoursePlan.objects.create(
            course=self.course,
            name="Premium",
            code="premium",
            price="3490.00",
            access_duration_days=365,
            is_active=True,
        )

    # ── privátní helpery ─────────────────────────────────────────────────────

    def _build_combined_cart(self):
        """Přidá vodítko + kurz do košíku a zvolí Zásilkovnu."""
        self.client.post(
            reverse("payments:add_variant_to_cart", args=[self.variant.id])
        )
        self.client.post(
            reverse("payments:add_course_to_cart", args=[self.plan.id])
        )
        self.client.post(
            reverse("payments:shipping"),
            {
                "shipping_method": Order.ShippingMethod.ZASILKOVNA,
                "packeta_point_id": "55500",
                "packeta_point_name": "Z-BOX Ostrava Centrum",
            },
        )

    def _post_checkout(self):
        data = _checkout_data("kombinovany@example.com", "Tomáš", "Pospíšil")
        return self.client.post(reverse("payments:contact_details"), data)

    # ── testy ────────────────────────────────────────────────────────────────

    def test_01_combined_cart_contains_both_items(self):
        """Košík obsahuje vodítko i kurz a metoda contains_physical_product() vrátí True."""
        self.client.post(
            reverse("payments:add_variant_to_cart", args=[self.variant.id])
        )
        self.client.post(
            reverse("payments:add_course_to_cart", args=[self.plan.id])
        )

        cart = Order.objects.get(status=Order.Status.CART)
        self.assertEqual(cart.items.count(), 2)
        self.assertTrue(cart.contains_physical_product())
        self.assertTrue(cart.items.filter(product_variant=self.variant).exists())
        self.assertTrue(cart.items.filter(course_plan=self.plan).exists())

    def test_02_checkout_requires_shipping_before_contact_details(self):
        """Smíšený košík (fyzický + digitální) musí projít výběrem dopravy."""
        self.client.post(
            reverse("payments:add_variant_to_cart", args=[self.variant.id])
        )
        self.client.post(
            reverse("payments:add_course_to_cart", args=[self.plan.id])
        )

        response = self.client.get(reverse("payments:contact_details"))

        self.assertRedirects(response, reverse("payments:shipping"))

    def test_03_combined_cart_total_price_includes_shipping(self):
        """Celková cena přes 1500 Kč => doprava Zásilkovnou je zdarma."""
        self._build_combined_cart()

        cart = Order.objects.get(status=Order.Status.CART)
        self.assertEqual(cart.shipping_price, Decimal("0.00"))
        expected = Decimal("1590.00") + Decimal("3490.00")
        self.assertEqual(cart.total_price, expected)

    def test_04_checkout_post_creates_stripe_session(self):
        """POST /checkout/ přesměruje na Stripe (kombinovaný košík)."""
        self._build_combined_cart()
        fake_session = _fake_stripe_session()
        with patch("payments.views.stripe.checkout.Session.create", return_value=fake_session):
            response = self._post_checkout()

        self.assertRedirects(response, fake_session.url, fetch_redirect_response=False)
        order = Order.objects.get(stripe_checkout_session_id="cs_test_abc123")
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_05_webhook_reduces_stock_and_grants_course_access(self):
        """
        Webhook na kombinovaný košík:
        - objednávka → PAID
        - sklad vodítka se sníží o 1
        - CourseAccess ke kurzu je udělen
        - zásilka Packeta je vytvořena (Zásilkovna)
        - potvrzovací email odeslán
        """
        self._build_combined_cart()
        fake_session = _fake_stripe_session()
        with patch("payments.views.stripe.checkout.Session.create", return_value=fake_session):
            self._post_checkout()

        order = Order.objects.get(stripe_checkout_session_id="cs_test_abc123")

        response, mock_packet = _fire_webhook(self.client, order.id)

        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertTrue(order.stock_reduced)

        # Sklad vodítka: bylo 4, koupena 1 → 3
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)

        # Uživatel vytvořen
        user = User.objects.get(email="kombinovany@example.com")
        self.assertEqual(user.first_name, "Tomáš")

        # CourseAccess udělen
        access = CourseAccess.objects.get(user=user, course=self.course)
        self.assertTrue(access.is_active)
        self.assertEqual(access.plan, self.plan)
        self.assertIsNotNone(access.expires_at)

        # Packeta zavolána (je fyzická Zásilkovna)
        mock_packet.assert_called_once()

        # Potvrzovací email zákazníkovi + interní upozornění na info@calmdog.cz
        self.assertEqual(len(mail.outbox), 2)
        recipients = [email.to[0] for email in mail.outbox]
        self.assertIn("kombinovany@example.com", recipients)
        self.assertIn("info@calmdog.cz", recipients)

    def test_06_webhook_retry_does_not_duplicate_stock_reduction_or_access(self):
        """
        Opakovaný webhook:
        - sklad se sníží jen jednou (díky stock_reduced flag)
        - CourseAccess se nevytvoří podruhé (update_or_create)
        """
        self._build_combined_cart()
        fake_session = _fake_stripe_session()
        with patch("payments.views.stripe.checkout.Session.create", return_value=fake_session):
            self._post_checkout()

        order = Order.objects.get(stripe_checkout_session_id="cs_test_abc123")

        # První webhook
        _fire_webhook(self.client, order.id)
        # Druhý webhook (simulace Stripe retry)
        _fire_webhook(self.client, order.id)

        # Sklad se snížil jen jednou (4 - 1 = 3)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock, 3)

        # Jen jeden CourseAccess
        user = User.objects.get(email="kombinovany@example.com")
        self.assertEqual(
            CourseAccess.objects.filter(user=user, course=self.course).count(),
            1,
        )
