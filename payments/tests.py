from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from courses.models import Course, CoursePlan
from payments.models import Order, OrderItem
from shop.models import Color, Product, ProductVariant


class ShippingViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            email="tester@example.com",
            password="test-password-123",
        )
        self.client.force_login(self.user)
        self.product = Product.objects.create(
            name="Voditko",
            slug="voditko",
        )
        self.color = Color.objects.create(name="Cerna")
        self.variant = ProductVariant.objects.create(
            product=self.product,
            color=self.color,
            length="7",
            type="no_loop",
            price="599.00",
            stock=5,
        )

    def create_cart(self):
        cart = Order.objects.create(
            user=self.user,
            status=Order.Status.CART,
        )
        OrderItem.objects.create(
            order=cart,
            product_variant=self.variant,
            quantity=1,
            price_at_purchase="599.00",
        )
        return cart

    def test_zasilkovna_requires_pickup_point(self):
        cart = self.create_cart()

        response = self.client.post(reverse("payments:shipping"), {
            "shipping_method": Order.ShippingMethod.ZASILKOVNA,
        })

        cart.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Pro Zásilkovnu vyber výdejní místo.")
        self.assertIsNone(cart.shipping_method)
        self.assertFalse(cart.packeta_point_id)

    def test_zasilkovna_saves_pickup_point(self):
        cart = self.create_cart()

        response = self.client.post(reverse("payments:shipping"), {
            "shipping_method": Order.ShippingMethod.ZASILKOVNA,
            "packeta_point_id": "12345",
            "packeta_point_name": "Z-BOX Praha Andel",
        })

        cart.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("payments:contact_details"))
        self.assertEqual(cart.shipping_method, Order.ShippingMethod.ZASILKOVNA)
        self.assertEqual(str(cart.shipping_price), "79.00")
        self.assertEqual(cart.packeta_point_id, "12345")
        self.assertEqual(cart.packeta_point_name, "Z-BOX Praha Andel")

    def test_guest_can_open_shipping_for_physical_cart(self):
        self.client.logout()

        cart = Order.objects.create(status=Order.Status.CART)
        OrderItem.objects.create(
            order=cart,
            product_variant=self.variant,
            quantity=1,
            price_at_purchase="599.00",
        )

        session = self.client.session
        session["cart_id"] = cart.id
        session.save()

        response = self.client.get(reverse("payments:shipping"))

        self.assertEqual(response.status_code, 200)


class CheckoutConfigTests(TestCase):
    @override_settings(STRIPE_SECRET_KEY="pk_test_invalid")
    def test_checkout_rejects_publishable_key_as_secret_on_submit(self):
        course = Product.objects.create(name="Kurz produkt", slug="kurz-produkt")
        color = Color.objects.create(name="Sediva")
        variant = ProductVariant.objects.create(
            product=course,
            color=color,
            length="7",
            type="no_loop",
            price="599.00",
            stock=5,
        )
        cart = Order.objects.create(status=Order.Status.CART)
        OrderItem.objects.create(
            order=cart,
            product_variant=variant,
            quantity=1,
            price_at_purchase="599.00",
        )
        cart.shipping_method = Order.ShippingMethod.KURYR
        cart.shipping_price = "119.00"
        cart.save(update_fields=["shipping_method", "shipping_price"])
        session = self.client.session
        session["cart_id"] = cart.id
        session.save()

        response = self.client.post(reverse("payments:checkout"), {
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "phone": "123456789",
            "street": "Test 1",
            "city": "Praha",
            "zip_code": "11000",
            "country": "CZ",
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn("Neplatná konfigurace Stripe.", response.content.decode())

    @override_settings(STRIPE_WEBHOOK_SECRET="")
    def test_webhook_requires_secret_configuration(self):
        response = self.client.post(
            reverse("payments:stripe_webhook"),
            data="{}",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing webhook configuration", response.content.decode())


class CheckoutFlowTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Voditko",
            slug="voditko-flow",
        )
        self.color = Color.objects.create(name="Piskova")
        self.variant = ProductVariant.objects.create(
            product=self.product,
            color=self.color,
            length="7",
            type="no_loop",
            price="599.00",
            stock=5,
        )

    def create_session_cart(self, shipping_method=None):
        cart = Order.objects.create(
            status=Order.Status.CART,
            shipping_method=shipping_method,
            shipping_price="79.00" if shipping_method else "0.00",
            packeta_point_id="12345" if shipping_method == Order.ShippingMethod.ZASILKOVNA else None,
            packeta_point_name="Z-BOX Praha Andel" if shipping_method == Order.ShippingMethod.ZASILKOVNA else None,
        )
        OrderItem.objects.create(
            order=cart,
            product_variant=self.variant,
            quantity=1,
            price_at_purchase="599.00",
        )
        session = self.client.session
        session["cart_id"] = cart.id
        session.save()
        return cart

    @override_settings(STRIPE_SECRET_KEY="sk_test_valid")
    def test_checkout_redirects_to_shipping_when_physical_order_has_no_shipping(self):
        self.create_session_cart()

        response = self.client.get(reverse("payments:contact_details"))

        self.assertRedirects(response, reverse("payments:shipping"))

    @override_settings(STRIPE_SECRET_KEY="sk_test_valid")
    def test_checkout_renders_after_shipping_selection(self):
        self.create_session_cart(shipping_method=Order.ShippingMethod.ZASILKOVNA)

        response = self.client.get(reverse("payments:contact_details"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Zvolená doprava")
        self.assertContains(response, "Z-BOX Praha Andel")


class BundleCartTests(TestCase):
    def setUp(self):
        self.leash = Product.objects.create(
            name="Vodítko bez očka",
            slug="voditko-bez-ocka",
            is_active=True,
        )
        self.loop = Product.objects.create(
            name="Samostatné očko",
            slug="samostatne-ocko",
            is_active=True,
        )
        self.gray = Color.objects.create(name="Šedá")
        self.pink = Color.objects.create(name="Pastelově růžová")
        self.leash_variant = ProductVariant.objects.create(
            product=self.leash,
            color=self.gray,
            length="7",
            type="no_loop",
            price="1490.00",
            stock=2,
            is_active=True,
        )
        self.loop_variant = ProductVariant.objects.create(
            product=self.loop,
            color=self.gray,
            type="shoulder",
            price="700.00",
            stock=1,
            is_active=True,
        )
        self.loop_variant_other_color = ProductVariant.objects.create(
            product=self.loop,
            color=self.pink,
            type="shoulder",
            price="800.00",
            stock=1,
            is_active=True,
        )

    def test_bundle_adds_both_matching_items_to_cart(self):
        response = self.client.post(
            reverse("payments:add_bundle_to_cart", args=[self.leash_variant.id]),
            {"bundle_variant_id": self.loop_variant.id},
        )

        self.assertRedirects(response, reverse("payments:cart_detail"))
        cart = Order.objects.get(status=Order.Status.CART)
        self.assertEqual(cart.items.count(), 2)
        self.assertTrue(cart.items.filter(product_variant=self.leash_variant).exists())
        self.assertTrue(cart.items.filter(product_variant=self.loop_variant).exists())

    def test_bundle_rejects_mismatched_color(self):
        response = self.client.post(
            reverse("payments:add_bundle_to_cart", args=[self.leash_variant.id]),
            {"bundle_variant_id": self.loop_variant_other_color.id},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Bundle musí mít shodnou barvu", response.content.decode())
        self.assertFalse(Order.objects.filter(status=Order.Status.CART).exists())


class CourseCartTests(TestCase):
    def setUp(self):
        self.course_one = Course.objects.create(title="Kurz 1", slug="kurz-1")
        self.course_two = Course.objects.create(title="Kurz 2", slug="kurz-2")
        self.plan_one = CoursePlan.objects.create(
            course=self.course_one,
            name="Standard",
            code="standard",
            price="1490.00",
            access_duration_days=180,
            is_active=True,
        )
        self.plan_two = CoursePlan.objects.create(
            course=self.course_two,
            name="Standard",
            code="standard",
            price="2490.00",
            access_duration_days=180,
            is_active=True,
        )

    def test_guest_can_add_course_to_cart_by_plan_id(self):
        response = self.client.post(
            reverse("payments:add_course_to_cart", args=[self.plan_one.id])
        )

        self.assertRedirects(response, reverse("payments:cart_detail"))
        cart = Order.objects.get(status=Order.Status.CART)
        item = cart.items.get()
        self.assertEqual(item.course_plan, self.plan_one)
        self.assertEqual(str(item.price_at_purchase), "1490.00")

    def test_add_course_to_cart_uses_plan_id_even_when_codes_repeat(self):
        self.client.post(reverse("payments:add_course_to_cart", args=[self.plan_two.id]))

        cart = Order.objects.get(status=Order.Status.CART)
        item = cart.items.get()
        self.assertEqual(item.course_plan, self.plan_two)
