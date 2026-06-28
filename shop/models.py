from django.db import models
from django.conf import settings


# ======================================
# PRODUCT
# ======================================

class Product(models.Model):
    name = models.CharField("Název produktu", max_length=200)
    slug = models.SlugField("Slug", unique=True)
    description = models.TextField("Popis", blank=True)
    image = models.ImageField("Obrázek", upload_to="products/", blank=True)
    is_active = models.BooleanField("Aktivní", default=True)

    created_at = models.DateTimeField("Vytvořeno", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Produkt"
        verbose_name_plural = "Produkty"

    def __str__(self):
        return self.name


# ======================================
# COLOR
# ======================================

class Color(models.Model):
    name = models.CharField("Název barvy", max_length=50)
    hex_code = models.CharField("HEX kód", max_length=7, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Barva"
        verbose_name_plural = "Barvy"

    def __str__(self):
        return self.name


# ======================================
# PRODUCT VARIANT
# ======================================

class ProductVariant(models.Model):

    LENGTH_CHOICES = [
        ("7", "7 metrů"),
        ("10", "10 metrů"),
    ]

    TYPE_CHOICES = [
        ("no_loop", "Bez očka"),
        ("shoulder", "Očko přes rameno"),
        ("hand_loop", "Poutko na ruku"),
    ]

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        verbose_name="Produkt"
    )

    length = models.CharField(
        "Délka",
        max_length=5,
        choices=LENGTH_CHOICES,
        null=True,
        blank=True
    )

    type = models.CharField(
        "Typ zakončení",
        max_length=20,
        choices=TYPE_CHOICES,
        null=True,
        blank=True
    )

    color = models.ForeignKey(
        Color,
        on_delete=models.CASCADE,
        verbose_name="Barva"
    )

    price = models.DecimalField(
        "Cena",
        max_digits=10,
        decimal_places=2
    )

    stock = models.PositiveIntegerField(
        "Sklad",
        default=0
    )

    is_active = models.BooleanField("Aktivní", default=True)

    created_at = models.DateTimeField("Vytvořeno", auto_now_add=True)

    class Meta:
        unique_together = ("product", "length", "type", "color")
        ordering = ["product", "length", "type"]
        verbose_name = "Varianta produktu"
        verbose_name_plural = "Varianty produktů"

        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["is_active"]),
        ]

    # ==============================
    # BUSINESS LOGIC
    # ==============================

    def is_in_stock(self):
        return self.stock > 0

    def reduce_stock(self, quantity):
        """
        Bezpečné odečtení skladu.
        Používat při dokončení objednávky.
        """
        if quantity > self.stock:
            raise ValueError("Nedostatek zboží na skladě.")

        self.stock -= quantity
        self.save(update_fields=["stock"])

    def __str__(self):
        return (
            f"{self.product.name} – "
            f"{self.get_length_display()} – "
            f"{self.get_type_display()} – "
            f"{self.color.name}"
        )


# ======================================
# CART ITEM
# ======================================

class CartItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
        verbose_name="Zákazník",
    )

    product_variant = models.ForeignKey(
        "shop.ProductVariant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Varianta produktu",
    )

    course_plan = models.ForeignKey(
        "courses.CoursePlan",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Varianta kurzu",
    )

    quantity = models.PositiveIntegerField("Množství", default=1)
    created_at = models.DateTimeField("Vytvořeno", auto_now_add=True)

    class Meta:
        verbose_name = "Položka košíku"
        verbose_name_plural = "Položky košíku"

    def get_price(self):
        if self.product_variant:
            return self.product_variant.price
        if self.course_plan:
            return self.course_plan.price
        return 0

    def get_total_price(self):
        return self.get_price() * self.quantity

    def __str__(self):
        if self.product_variant:
            return f"{self.user.email} – {self.product_variant}"
        if self.course_plan:
            return f"{self.user.email} – {self.course_plan}"
        return f"{self.user.email} – Unknown item"
