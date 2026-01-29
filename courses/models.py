from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.conf import settings
from django.db import models



# --- Validators ---

vimeo_validator = RegexValidator(
    regex=r"^https:\/\/player\.vimeo\.com\/video\/\d+.*$",
    message="Zadej Vimeo embed URL ve tvaru https://player.vimeo.com/video/123456789"
)


def validate_pdf(file):
    if not file.name.lower().endswith(".pdf"):
        raise ValidationError("Soubor musí být PDF.")


# --- Models ---

class Course(models.Model):
    title = models.CharField(max_length=200, default="Kurz")
    public_intro = models.TextField(blank=True)
    about_text = models.TextField(blank=True)
    private_intro = models.TextField(blank=True)

    def __str__(self):
        return self.title


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="modules")
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)

    intro_text = models.TextField(blank=True)  # Povídání k modulu

    # Vimeo embed URL (povolíme jen player.vimeo.com/video/ID...)
    vimeo_embed_url1 = models.URLField(blank=True, validators=[vimeo_validator])
    vimeo_embed_url2 = models.URLField(blank=True, validators=[vimeo_validator])
    vimeo_embed_url3 = models.URLField(blank=True, validators=[vimeo_validator])

    # PDF (pouze .pdf)
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
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title) or "modul"
            slug = base
            i = 2
            while Module.objects.filter(slug=slug).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order}. {self.title}"


User = settings.AUTH_USER_MODEL


class ModuleProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    module = models.ForeignKey("Module", on_delete=models.CASCADE)

    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "module")
