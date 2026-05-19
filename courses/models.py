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


# ======================================
# COURSE
# ======================================

class Course(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)

    public_intro = models.TextField(blank=True)
    about_text = models.TextField(blank=True)
    private_intro = models.TextField(blank=True)

    image = models.ImageField(upload_to="courses/", blank=True)

    is_active = models.BooleanField(default=True)

    coming_soon = models.BooleanField(
        default=False,
        help_text="Kurz se připravuje – zobrazí se informace a tlačítko Přidat do košíku bude skryté.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
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
        related_name="plans"
    )

    name = models.CharField(max_length=100)  # Standard / Premium
    code = models.SlugField(db_index=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)

    includes_certificate = models.BooleanField(default=False)
    includes_consultation = models.BooleanField(default=False)

    # 🔥 délka přístupu v dnech (default 180 = půl roku)
    access_duration_days = models.PositiveIntegerField(default=180)

    is_active = models.BooleanField(default=True)

    class Meta:
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
        related_name="modules"
    )

    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)

    slug = models.SlugField(max_length=220, blank=True)

    intro_text = models.TextField(blank=True)

    vimeo_embed_url1 = models.URLField(blank=True, validators=[vimeo_validator])
    vimeo_embed_url2 = models.URLField(blank=True, validators=[vimeo_validator])
    vimeo_embed_url3 = models.URLField(blank=True, validators=[vimeo_validator])

    pdf_file = models.FileField(
        upload_to="module_pdfs/",
        blank=True,
        null=True,
        validators=[validate_pdf],
    )

    class Meta:
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    module = models.ForeignKey("Module", on_delete=models.CASCADE)

    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    module = models.ForeignKey("Module", on_delete=models.CASCADE, related_name="quiz_progresses")

    step = models.PositiveSmallIntegerField()
    attempts_count = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(default=False)
    passed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "module", "step")
        indexes = [
            models.Index(fields=["user", "module"]),
            models.Index(fields=["module", "step"]),
        ]

    def __str__(self):
        return f"{self.user} – {self.module} – krok {self.step}"
