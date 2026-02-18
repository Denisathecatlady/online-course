from django.db import models
from django.conf import settings
from django.utils import timezone
from courses.models import Course


class CoursePlan(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=200)

    subtitle = models.CharField(
        max_length=255,
        blank=True,
        help_text="Krátký podtitulek pod názvem (např. Bez konzultace • Bez certifikátu)"
    )

    description = models.TextField(
        blank=True,
        help_text="Textový popis varianty (volitelné)"
    )

    bullets = models.TextField(
        blank=True,
        help_text="Jedna položka na řádek – zobrazí se jako seznam"
    )

    price_czk = models.PositiveIntegerField()

    includes_consultation = models.BooleanField(default=False)
    includes_certificate = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    @property
    def bullets_list(self):
        return [line.strip() for line in self.bullets.splitlines() if line.strip()]

    def __str__(self):
        return self.name


class Order(models.Model):
    class Status(models.TextChoices):
        CART = "cart", "Košík"
        PENDING = "pending", "Čeká na platbu"
        PAID = "paid", "Zaplaceno"
        FAILED = "failed", "Neúspěšné"
        CANCELED = "canceled", "Zrušeno"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="orders")
    plan = models.ForeignKey(CoursePlan, on_delete=models.PROTECT, related_name="orders")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CART)
    created_at = models.DateTimeField(auto_now_add=True)


    # kdo nakupuje
    buyer_email = models.EmailField()
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40, blank=True)

    newsletter_opt_in = models.BooleanField(
            default=False,
            help_text="Souhlas se zasíláním newsletteru"
        )
    # adresa (dodací / kontaktní)
    street = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2, default="CZ")  # ISO: CZ

    # fakturační údaje (pokud se liší)
    invoice_name = models.CharField(max_length=255, blank=True)   # firma/jméno na faktuře
    invoice_street = models.CharField(max_length=255, blank=True)
    invoice_city = models.CharField(max_length=120, blank=True)
    invoice_zip = models.CharField(max_length=20, blank=True)
    invoice_country = models.CharField(max_length=2, default="CZ", blank=True)

    # Stripe
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True, default="")
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, default="")


    # číslo faktury (od 260001)
    invoice_number = models.PositiveIntegerField(
    unique=True,
    null=True,
    blank=True,
    help_text="Číslo faktury – generuje se po zaplacení"
)


    # faktura PDF (volitelné)
    invoice_pdf = models.FileField(upload_to="invoices/", blank=True, null=True)

    def __str__(self):
        return f"Order #{self.pk} - {self.buyer_email} - {self.plan} - {self.status}"



class CourseAccess(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_accesses"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="accesses")
    plan = models.ForeignKey(CoursePlan, on_delete=models.PROTECT, related_name="accesses")

    is_active = models.BooleanField(default=True)
    granted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("user", "course")]

    def __str__(self) -> str:
        return f"{self.user} → {self.course} ({self.plan.code})"

# ======================================
# PRODUCT (univerzální produkt systému)
# ======================================

class Product(models.Model):
    PRODUCT_TYPES = (
        ("course", "Course"),
        ("physical", "Physical"),
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    price_czk = models.PositiveIntegerField()

    product_type = models.CharField(max_length=20, choices=PRODUCT_TYPES)

    # Pokud je to kurz
    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="product"
    )

    # Pouze pro fyzické produkty
    stock = models.PositiveIntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ======================================
# ORDER ITEM (více položek v objednávce)
# ======================================

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT
    )

    quantity = models.PositiveIntegerField(default=1)

    price_at_purchase = models.PositiveIntegerField()

    def total_price(self):
        return self.quantity * self.price_at_purchase

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
