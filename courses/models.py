from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.conf import settings


# ======================================
# VALIDÁTORY
# ======================================

vimeo_validator = RegexValidator(
    regex=r"^https:\/\/player\.vimeo\.com\/video\/\d+.*$",
    message="Zadej Vimeo embed URL ve tvaru https://player.vimeo.com/video/123456789"
)


def validate_pdf(file):
    if not file.name.lower().endswith(".pdf"):
        raise ValidationError("Soubor musí být PDF.")

    header = file.read(5)
    file.seek(0)
    if header != b"%PDF-":
        raise ValidationError("Soubor není platné PDF.")


# ======================================
# COURSE
# ======================================

class Course(models.Model):
    title = models.CharField("Název kurzu", max_length=200)
    slug = models.SlugField("URL adresa (slug)", unique=True, blank=True)

    public_intro = models.TextField("Veřejný úvod", blank=True)
    about_text = models.TextField("O kurzu", blank=True)
    private_intro = models.TextField("Úvod po zakoupení", blank=True)

    image = models.ImageField("Obrázek kurzu", upload_to="courses/", blank=True)

    is_active = models.BooleanField("Aktivní", default=True)

    coming_soon = models.BooleanField(
        "Připravujeme",
        default=False,
        help_text="Kurz se připravuje – zobrazí se informace a tlačítko Přidat do košíku bude skryté.",
    )

    created_at = models.DateTimeField("Vytvořeno", auto_now_add=True)

    class Meta:
        verbose_name = "Kurz"
        verbose_name_plural = "Kurzy"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "kurz"
            slug = base
            i = 2
            while Course.objects.filter(slug=slug).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# ======================================
# COURSE PLAN (varianty kurzu)
# ======================================

class CoursePlan(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="plans",
        verbose_name="Kurz",
    )

    name = models.CharField("Název varianty", max_length=100)  # Standard / Premium
    code = models.SlugField("Kód varianty", db_index=True)

    price = models.DecimalField("Cena", max_digits=10, decimal_places=2)

    includes_certificate = models.BooleanField("Obsahuje certifikát", default=False)
    includes_consultation = models.BooleanField("Obsahuje konzultaci", default=False)

    access_duration_days = models.PositiveIntegerField(
        "Délka přístupu (dny)",
        default=180,
        help_text="Po kolika dnech od zakoupení přístup vyprší (180 = půl roku).",
    )

    is_active = models.BooleanField("Aktivní", default=True)

    class Meta:
        verbose_name = "Varianta kurzu"
        verbose_name_plural = "Varianty kurzu"
        unique_together = ("course", "code")
        indexes = [
            models.Index(fields=["course"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.course.title} – {self.name}"


# ======================================
# MODULE
# ======================================

class Module(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="modules",
        verbose_name="Kurz",
    )

    order = models.PositiveSmallIntegerField("Pořadí")
    title = models.CharField("Název modulu", max_length=200)

    slug = models.SlugField("URL adresa (slug)", max_length=220, blank=True)

    intro_text = models.TextField("Úvodní text", blank=True)

    vimeo_embed_url1 = models.URLField("Vimeo video 1", blank=True, validators=[vimeo_validator])
    vimeo_embed_url2 = models.URLField("Vimeo video 2", blank=True, validators=[vimeo_validator])
    vimeo_embed_url3 = models.URLField("Vimeo video 3", blank=True, validators=[vimeo_validator])

    pdf_file = models.FileField(
        "PDF materiál",
        upload_to="module_pdfs/",
        blank=True,
        null=True,
        validators=[validate_pdf],
    )

    class Meta:
        verbose_name = "Modul"
        verbose_name_plural = "Moduly"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["course", "order"], name="unique_order_per_course"),
            models.UniqueConstraint(fields=["course", "slug"], name="unique_slug_per_course"),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "modul"
            slug = base
            i = 2
            while Module.objects.filter(course=self.course, slug=slug).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order}. {self.title}"


# ======================================
# MODULE PROGRESS
# ======================================

class ModuleProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Zákazník")
    module = models.ForeignKey("Module", on_delete=models.CASCADE, verbose_name="Modul")

    completed = models.BooleanField("Dokončeno", default=False)
    completed_at = models.DateTimeField("Dokončeno dne", null=True, blank=True)

    class Meta:
        verbose_name = "Postup v modulu"
        verbose_name_plural = "Postup v modulech"
        unique_together = ("user", "module")
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["module"]),
        ]

    def __str__(self):
        return f"{self.user} – {self.module}"


# ======================================
# MODULE QUIZ PROGRESS
# ======================================

class ModuleQuizProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Zákazník")
    module = models.ForeignKey("Module", on_delete=models.CASCADE, related_name="quiz_progresses", verbose_name="Modul")

    step = models.PositiveSmallIntegerField("Krok kvízu")
    attempts_count = models.PositiveIntegerField("Počet pokusů", default=0)
    passed = models.BooleanField("Splněno", default=False)
    passed_at = models.DateTimeField("Splněno dne", null=True, blank=True)

    class Meta:
        verbose_name = "Postup v kvízu"
        verbose_name_plural = "Postup v kvízech"
        unique_together = ("user", "module", "step")
        indexes = [
            models.Index(fields=["user", "module"]),
            models.Index(fields=["module", "step"]),
        ]

    def __str__(self):
        return f"{self.user} – {self.module} – krok {self.step}"
