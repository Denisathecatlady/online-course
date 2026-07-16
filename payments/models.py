from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone
from datetime import timedelta

# Soukromé úložiště pro faktury a přepravní štítky – mimo MEDIA_ROOT, takže
# tyto soubory nejde stáhnout přímou URL (viz PRIVATE_MEDIA_ROOT v settings).
# Přístup výhradně přes chráněné view s kontrolou vlastníka objednávky.
private_storage = FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT)


# ======================================
# SHOP SETTINGS (singleton)
# ======================================

class ShopSettings(models.Model):
    """
    Singleton – vždy existuje právě jeden řádek (pk=1).
    Přepínač shop_locked lze ovládat přímo z adminu.
    """
    shop_locked = models.BooleanField(
        "Prodej uzamčen",
        default=False,
        help_text=(
            "Zaškrtněte pro docasne uzamceni kosiku a tlacítek Pridat do kosiku. "
            "Stranky kurzu a produktu zustavaji dostupne. "
            "Existujici pristupy ke kurzum nejsou dotceny."
        ),
    )

    class Meta:
        verbose_name = "Nastavení obchodu"
        verbose_name_plural = "Nastavení obchodu"

    def __str__(self):
        return "Nastavení obchodu"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # singleton – nelze smazat

    @classmethod
    def is_locked(cls):
        """Vrací True pokud je prodej uzamčen (DB nebo env proměnná)."""
        # Env proměnná SHOP_LOCKED=1 má vždy přednost (tvrdý override)
        if getattr(settings, "SHOP_LOCKED", False):
            return True
        # transaction.atomic() izoluje případnou ProgrammingError (tabulka ještě neexistuje)
        # do savePointu – PostgreSQL spojení zůstane použitelné i po chybě.
        try:
            with transaction.atomic():
                obj, _ = cls.objects.get_or_create(pk=1)
                return obj.shop_locked
        except Exception:
            return False


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

    FREE_SHIPPING_THRESHOLD = Decimal("1500")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="Zákazník",
    )

    status = models.CharField(
        "Stav objednávky",
        max_length=20,
        choices=Status.choices,
        default=Status.CART,
    )

    created_at = models.DateTimeField("Vytvořeno", auto_now_add=True)
    paid_at = models.DateTimeField("Zaplaceno", null=True, blank=True)
    review_request_sent_at = models.DateTimeField("Žádost o recenzi odeslána", null=True, blank=True)

    # ==============================
    # KONTAKT
    # ==============================

    buyer_email = models.EmailField("E-mail", blank=True)
    first_name = models.CharField("Jméno", max_length=120, blank=True)
    last_name = models.CharField("Příjmení", max_length=120, blank=True)
    phone = models.CharField("Telefon", max_length=40, blank=True)
    newsletter_opt_in = models.BooleanField("Přihlášen k newsletteru", default=False)

    # ==============================
    # DORUČOVACÍ ADRESA
    # ==============================

    street = models.CharField("Ulice a číslo", max_length=255, blank=True)
    city = models.CharField("Město", max_length=120, blank=True)
    zip_code = models.CharField("PSČ", max_length=20, blank=True)
    country = models.CharField("Země", max_length=2, default="CZ")

    # ==============================
    # FAKTURAČNÍ ADRESA
    # ==============================

    invoice_name = models.CharField("Fakturační jméno / firma", max_length=255, blank=True)
    invoice_street = models.CharField("Fakturační ulice", max_length=255, blank=True)
    invoice_city = models.CharField("Fakturační město", max_length=120, blank=True)
    invoice_zip = models.CharField("Fakturační PSČ", max_length=20, blank=True)
    invoice_country = models.CharField("Fakturační země", max_length=2, default="CZ", blank=True)
    invoice_ico = models.CharField("IČO", max_length=20, blank=True)

    # ==============================
    # DOPRAVA
    # ==============================

    shipping_method = models.CharField(
        "Způsob dopravy",
        max_length=50,
        choices=ShippingMethod.choices,
        null=True,
        blank=True,
    )

    shipping_price = models.DecimalField(
        "Cena dopravy",
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    # ==============================
    # SLEVOVÝ KUPÓN
    # ==============================

    coupon = models.ForeignKey(
        "Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
        verbose_name="Použitý kupón",
    )

    discount_amount = models.DecimalField(
        "Sleva",
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Výše slevy z kupónu uplatněná na tuto objednávku.",
    )

    # ==============================
    # PACKETA
    # ==============================

    packeta_packet_id = models.CharField("Packeta – ID zásilky", max_length=100, blank=True, null=True)
    packeta_tracking_number = models.CharField("Packeta – sledovací číslo", max_length=100, blank=True, null=True)
    packeta_label_pdf = models.FileField("Packeta – štítek (PDF)", upload_to="packeta_labels/", storage=private_storage, blank=True, null=True)
    packeta_point_id = models.CharField("Packeta – ID výdejního místa", max_length=100, blank=True, null=True)
    packeta_point_name = models.CharField("Packeta – výdejní místo", max_length=255, blank=True, null=True)

    packeta_created_at = models.DateTimeField("Packeta – vytvořeno", blank=True, null=True)

    # ==============================
    # STRIPE
    # ==============================

    stripe_checkout_session_id = models.CharField("Stripe – ID platební relace", max_length=255, blank=True, default="")
    stripe_payment_intent_id = models.CharField("Stripe – ID platby", max_length=255, blank=True, default="")

    # ==============================
    # FAKTURA
    # ==============================

    invoice_number = models.PositiveIntegerField(
        "Číslo faktury",
        unique=True,
        null=True,
        blank=True,
    )

    invoice_pdf = models.FileField("Faktura (PDF)", upload_to="invoices/", storage=private_storage, blank=True, null=True)

    # ==============================
    # BUSINESS LOGIC
    # ==============================

    stock_reduced = models.BooleanField("Sklad odečten", default=False)

    class Meta:
        verbose_name = "Objednávka"
        verbose_name_plural = "Objednávky"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Objednávka #{self.pk}"

    @property
    def items_total(self):
        return sum((item.subtotal for item in self.items.all()), Decimal("0"))

    @property
    def qualifies_for_free_shipping(self):
        return self.items_total >= self.FREE_SHIPPING_THRESHOLD

    @property
    def total_price(self):
        total = self.items_total + self.shipping_price - self.discount_amount
        return max(total, Decimal("0"))

    def contains_physical_product(self):
        return self.items.filter(product_variant__isnull=False).exists()

    def contains_course(self):
        return self.items.filter(course_plan__isnull=False).exists()

    # ----------------------
    # SLEVOVÝ KUPÓN – pomocné metody
    # ----------------------

    def apply_coupon(self, coupon):
        """Uplatní kupón na objednávku a přepočítá slevu."""
        self.coupon = coupon
        self.discount_amount = coupon.compute_discount(self)
        self.save(update_fields=["coupon", "discount_amount"])

    def clear_coupon(self):
        """Odebere kupón z objednávky."""
        self.coupon = None
        self.discount_amount = Decimal("0")
        self.save(update_fields=["coupon", "discount_amount"])

    def recalculate_discount(self):
        """
        Přepočítá slevu podle aktuálního obsahu košíku.
        Pokud kupón už neplatí (změna položek, vypršení…), automaticky se odebere.
        """
        if not self.coupon_id:
            return
        ok, _ = self.coupon.validate_for(self, self.user)
        if ok:
            self.discount_amount = self.coupon.compute_discount(self)
        else:
            self.coupon = None
            self.discount_amount = Decimal("0")
        self.save(update_fields=["coupon", "discount_amount"])


# ======================================
# ORDER ITEM
# ======================================

class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Objednávka",
    )

    product_variant = models.ForeignKey(
        "shop.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Varianta produktu",
    )

    course_plan = models.ForeignKey(
        "courses.CoursePlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Varianta kurzu",
    )

    quantity = models.PositiveIntegerField("Množství", default=1)

    price_at_purchase = models.DecimalField(
        "Cena při nákupu",
        max_digits=10,
        decimal_places=2,
    )

    class Meta:
        verbose_name = "Položka objednávky"
        verbose_name_plural = "Položky objednávky"

    @property
    def subtotal(self):
        return self.quantity * self.price_at_purchase

    def __str__(self):
        if self.product_variant:
            return f"{self.product_variant} x {self.quantity}"
        if self.course_plan:
            return f"{self.course_plan} x {self.quantity}"
        return f"Položka #{self.id}"


# ======================================
# COURSE ACCESS
# ======================================

class CourseAccess(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_accesses",
        verbose_name="Zákazník",
    )

    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="accesses",
        verbose_name="Kurz",
    )

    plan = models.ForeignKey(
        "courses.CoursePlan",
        on_delete=models.PROTECT,
        related_name="accesses",
        null=True,
        blank=True,
        verbose_name="Zakoupená varianta",
    )

    granted_at = models.DateTimeField("Přístup udělen", default=timezone.now)
    expires_at = models.DateTimeField("Přístup vyprší", blank=True, null=True)

    is_active = models.BooleanField("Aktivní", default=True)
    bypass_module_sequencing = models.BooleanField(
        "Povolit přeskakování modulů",
        default=False,
        help_text="Pokud je zapnuto, zákazník nemusí procházet moduly v pořadí.",
    )

    class Meta:
        verbose_name = "Přístup ke kurzu"
        verbose_name_plural = "Přístupy ke kurzům"
        unique_together = ("user", "course")
        ordering = ["-granted_at"]

    def save(self, *args, **kwargs):
        # expires_at nastavujeme POUZE při vytvoření nového záznamu,
        # nikoli při editaci existujícího – jinak bychom retroaktivně
        # přepsali přístup stávajícím zákazníkům.
        if self.pk is None and not self.expires_at and self.plan_id:
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


# ======================================
# COUPON (slevový kupón)
# ======================================

class Coupon(models.Model):

    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Procentuální sleva (%)"
        FIXED = "fixed", "Pevná částka (Kč)"

    code = models.CharField(
        "Kód kupónu",
        max_length=40,
        unique=True,
        db_index=True,
        help_text="Kód, který zákazník zadá v košíku, např. VANOCE20.",
    )

    description = models.CharField(
        "Název / popis",
        max_length=255,
        blank=True,
        help_text="Krátký popis pro orientaci v seznamu kupónů.",
    )

    discount_type = models.CharField(
        "Typ slevy",
        max_length=10,
        choices=DiscountType.choices,
        default=DiscountType.PERCENT,
    )

    discount_value = models.DecimalField(
        "Výše slevy",
        max_digits=10,
        decimal_places=2,
        help_text="U procentuální slevy zadej číslo 0–100, u pevné částky hodnotu v Kč.",
    )

    # ----------------------
    # PLATNOST
    # ----------------------

    valid_from = models.DateTimeField("Platný od", null=True, blank=True)
    valid_to = models.DateTimeField("Platný do", null=True, blank=True)

    is_active = models.BooleanField("Aktivní", default=True)

    # ----------------------
    # POČTY POUŽITÍ
    # ----------------------

    max_uses = models.PositiveIntegerField(
        "Maximální počet použití",
        null=True,
        blank=True,
        help_text="Nech prázdné pro neomezené použití.",
    )

    used_count = models.PositiveIntegerField(
        "Počet použití",
        default=0,
        help_text="Kolikrát už byl kupón uplatněn (počítá se automaticky).",
    )

    max_uses_per_user = models.PositiveIntegerField(
        "Max. použití na jednoho zákazníka",
        null=True,
        blank=True,
        help_text="Nech prázdné, pokud nechceš omezovat počet použití na zákazníka.",
    )

    # ----------------------
    # OMEZENÍ
    # ----------------------

    min_order_value = models.DecimalField(
        "Minimální hodnota objednávky (Kč)",
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Kupón půjde uplatnit až od této hodnoty zboží v košíku.",
    )

    products = models.ManyToManyField(
        "shop.Product",
        blank=True,
        related_name="coupons",
        verbose_name="Platí pouze pro produkty",
        help_text="Nech prázdné = platí pro všechny produkty.",
    )

    courses = models.ManyToManyField(
        "courses.Course",
        blank=True,
        related_name="coupons",
        verbose_name="Platí pouze pro kurzy",
        help_text="Nech prázdné = platí pro všechny kurzy.",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personal_coupons",
        verbose_name="Platí pouze pro zákazníka",
        help_text="Nech prázdné = kupón může použít kdokoli.",
    )

    note = models.TextField("Interní poznámka", blank=True)

    created_at = models.DateTimeField("Vytvořeno", auto_now_add=True)

    class Meta:
        verbose_name = "Slevový kupón"
        verbose_name_plural = "Slevové kupóny"
        ordering = ["-created_at"]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        # Kódy kupónů sjednocujeme na velká písmena bez mezer,
        # ať zákazník nezadá omylem "vanoce20" nebo " VANOCE20 ".
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    # ----------------------
    # VÝPOČET SLEVY
    # ----------------------

    def _eligible_total(self, order):
        """
        Vrátí hodnotu položek v košíku, na které se kupón vztahuje.
        Bez omezení = celá hodnota zboží. S omezením = jen odpovídající položky.
        """
        has_product_restriction = self.products.exists()
        has_course_restriction = self.courses.exists()

        if not has_product_restriction and not has_course_restriction:
            return order.items_total

        allowed_product_ids = set(self.products.values_list("id", flat=True))
        allowed_course_ids = set(self.courses.values_list("id", flat=True))

        total = Decimal("0")
        for item in order.items.select_related("product_variant", "course_plan"):
            if (
                has_product_restriction
                and item.product_variant_id
                and item.product_variant.product_id in allowed_product_ids
            ):
                total += item.subtotal
            if (
                has_course_restriction
                and item.course_plan_id
                and item.course_plan.course_id in allowed_course_ids
            ):
                total += item.subtotal
        return total

    def compute_discount(self, order):
        """Vypočítá výši slevy pro danou objednávku (v Kč, zaokrouhleno na koruny)."""
        eligible = self._eligible_total(order)
        if eligible <= 0:
            return Decimal("0")

        if self.discount_type == self.DiscountType.PERCENT:
            pct = max(Decimal("0"), min(self.discount_value, Decimal("100")))
            discount = eligible * pct / Decimal("100")
        else:
            discount = min(self.discount_value, eligible)

        discount = discount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        discount = min(discount, eligible)
        return max(Decimal("0"), discount)

    # ----------------------
    # VALIDACE
    # ----------------------

    def validate_for(self, order, user=None):
        """
        Ověří, zda lze kupón uplatnit na danou objednávku.
        Vrací dvojici (ok: bool, zpráva: str) – zpráva je určená pro zákazníka.
        """
        now = timezone.now()

        if not self.is_active:
            return False, "Tento kupón není aktivní."

        if self.valid_from and now < self.valid_from:
            return False, "Tento kupón ještě není platný."

        if self.valid_to and now > self.valid_to:
            return False, "Platnost tohoto kupónu už vypršela."

        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False, "Tento kupón už byl vyčerpán."

        if self.user_id and (user is None or not user.is_authenticated or user.pk != self.user_id):
            return False, "Tento kupón je vázán na jiného zákazníka."

        if self.max_uses_per_user is not None and user is not None and user.is_authenticated:
            used_by_user = self.usages.filter(user=user).count()
            if used_by_user >= self.max_uses_per_user:
                return False, "Tento kupón jste už vyčerpali."

        if order.items_total < self.min_order_value:
            return False, f"Kupón platí až od objednávky za {self.min_order_value:.0f} Kč."

        if self.compute_discount(order) <= 0:
            return False, "Na položky ve vašem košíku tento kupón nelze uplatnit."

        return True, "Kupón byl úspěšně uplatněn."


# ======================================
# COUPON USAGE (historie použití kupónu)
# ======================================

class CouponUsage(models.Model):

    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="usages",
        verbose_name="Kupón",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coupon_usages",
        verbose_name="Zákazník",
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="coupon_usages",
        verbose_name="Objednávka",
    )

    discount_amount = models.DecimalField(
        "Uplatněná sleva (Kč)",
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    used_at = models.DateTimeField("Použito", auto_now_add=True)

    class Meta:
        verbose_name = "Použití kupónu"
        verbose_name_plural = "Použití kupónů"
        ordering = ["-used_at"]

    def __str__(self):
        return f"{self.coupon.code} – objednávka #{self.order_id}"


# ======================================
# WELCOME COUPON CLAIM
# ======================================

class WelcomeCouponClaim(models.Model):
    """
    Zaznamenává, že daný e-mail již obdržel uvítací slevový kupón.
    Unikátnost emailu zabrání opakovanému nároku ze stejné adresy.
    """
    email = models.EmailField(
        "E-mail",
        unique=True,
        db_index=True,
    )
    coupon = models.OneToOneField(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Vytvořený kupón",
        related_name="welcome_claim",
    )
    created_at = models.DateTimeField("Odesláno", auto_now_add=True)

    class Meta:
        verbose_name = "Uvítací sleva"
        verbose_name_plural = "Uvítací slevy"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.created_at:%Y-%m-%d})"


# ======================================
# ODBĚRATELÉ NEWSLETTERU
# ======================================

class NewsletterSubscriber(models.Model):
    """
    Čistý seznam kontaktů se souhlasem s newsletterem, oddělený od objednávek.
    Deduplikace přes unikátní e-mail – jeden člověk = jeden řádek.
    """
    email = models.EmailField("E-mail", unique=True, db_index=True)
    first_name = models.CharField("Jméno", max_length=120, blank=True)
    last_name = models.CharField("Příjmení", max_length=120, blank=True)
    is_subscribed = models.BooleanField("Odebírá", default=True)
    source = models.CharField("Zdroj souhlasu", max_length=50, default="checkout", blank=True)
    created_at = models.DateTimeField("Souhlas udělen", auto_now_add=True)
    updated_at = models.DateTimeField("Aktualizováno", auto_now=True)

    class Meta:
        verbose_name = "Odběratel newsletteru"
        verbose_name_plural = "Odběratelé newsletteru"
        ordering = ("-created_at",)

    def __str__(self):
        return self.email

    @classmethod
    def sync_from_order(cls, order):
        """
        Vloží/aktualizuje odběratele z objednávky. Volá se jen tehdy,
        když byl souhlas udělen (newsletter_opt_in=True).
        """
        email = (order.buyer_email or "").strip().lower()
        if not email:
            return None

        defaults = {"is_subscribed": True, "source": "checkout"}
        if order.first_name:
            defaults["first_name"] = order.first_name.strip()
        if order.last_name:
            defaults["last_name"] = order.last_name.strip()

        subscriber, _ = cls.objects.update_or_create(email=email, defaults=defaults)
        return subscriber
