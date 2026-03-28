from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


# ======================================
# ORDER
# ======================================

class Order(models.Model):

    # ----------------------
    # STATUS
    # ----------------------

    class Status(models.TextChoices):
        CART = "cart", "Košík"
        PENDING = "pending", "Čeká na platbu"
        PAID = "paid", "Zaplaceno"
        FAILED = "failed", "Neúspěšné"
        CANCELED = "canceled", "Zrušeno"

    # ----------------------
    # SHIPPING
    # ----------------------

    class ShippingMethod(models.TextChoices):
        ZASILKOVNA = "zasilkovna", "Zásilkovna"
        KURYR = "kuryr", "Kurýr"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CART
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # ==============================
    # KONTAKT
    # ==============================

    buyer_email = models.EmailField(blank=True)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    newsletter_opt_in = models.BooleanField(default=False)

    # ==============================
    # DORUČOVACÍ ADRESA
    # ==============================

    street = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2, default="CZ")

    # ==============================
    # FAKTURAČNÍ ADRESA
    # ==============================

    invoice_name = models.CharField(max_length=255, blank=True)
    invoice_street = models.CharField(max_length=255, blank=True)
    invoice_city = models.CharField(max_length=120, blank=True)
    invoice_zip = models.CharField(max_length=20, blank=True)
    invoice_country = models.CharField(max_length=2, default="CZ", blank=True)

    # ==============================
    # DOPRAVA
    # ==============================

    shipping_method = models.CharField(
        max_length=50,
        choices=ShippingMethod.choices,
        null=True,
        blank=True
    )

    shipping_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    # ==============================
    # PACKETA
    # ==============================

    packeta_packet_id = models.CharField(max_length=100, blank=True, null=True)
    packeta_tracking_number = models.CharField(max_length=100, blank=True, null=True)
    packeta_label_pdf = models.FileField(upload_to="packeta_labels/", blank=True, null=True)
    packeta_point_id = models.CharField(max_length=100, blank=True, null=True)
    packeta_point_name = models.CharField(max_length=255, blank=True, null=True)

    packeta_created_at = models.DateTimeField(blank=True, null=True)
    # ==============================
    # STRIPE
    # ==============================

    stripe_checkout_session_id = models.CharField(max_length=255, blank=True, default="")
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, default="")

    # ==============================
    # FAKTURA
    # ==============================

    invoice_number = models.PositiveIntegerField(
        unique=True,
        null=True,
        blank=True
    )

    invoice_pdf = models.FileField(upload_to="invoices/", blank=True, null=True)

    # ==============================
    # BUSINESS LOGIC
    # ==============================

    stock_reduced = models.BooleanField(default=False)

    @property
    def items_total(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def total_price(self):
        return self.items_total + self.shipping_price

    def contains_physical_product(self):
        return self.items.filter(product_variant__isnull=False).exists()

# ======================================
# ORDER ITEM
# ======================================

class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product_variant = models.ForeignKey(
        "shop.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    course_plan = models.ForeignKey(
        "courses.CoursePlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    quantity = models.PositiveIntegerField(default=1)

    price_at_purchase = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    @property
    def subtotal(self):
        return self.quantity * self.price_at_purchase

    def __str__(self):
        if self.product_variant:
            return f"{self.product_variant} x {self.quantity}"
        if self.course_plan:
            return f"{self.course_plan} x {self.quantity}"
        return f"Item #{self.id}"


# ======================================
# COURSE ACCESS
# ======================================

class CourseAccess(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_accesses"
    )

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="accesses"
    )

    plan = models.ForeignKey(
        "courses.CoursePlan",
        on_delete=models.PROTECT,
        related_name="accesses",
        null=True,
        blank=True,
    )

    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("user", "course")

    def save(self, *args, **kwargs):
        if not self.expires_at and self.plan_id:
            self.expires_at = self.granted_at + timedelta(
                days=self.plan.access_duration_days
            )
        super().save(*args, **kwargs)

    def has_access(self):
        if not self.is_active:
            return False
        if self.expires_at is None:
            return True
        return timezone.now() <= self.expires_at

    def __str__(self):
        return f"{self.user} → {self.course}"
