from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model


def validate_photo_size(file):
    max_bytes = 5 * 1024 * 1024  # 5 MB
    if file.size > max_bytes:
        raise ValidationError("Fotografie může mít maximálně 5 MB.")


class UserProfile(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Uživatel"
        ADMIN = "admin", "Admin"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Uživatel",
    )

    role = models.CharField(
        "Role",
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
    )

    phone = models.CharField("Telefon", max_length=40, blank=True)

    # doručovací adresa
    street = models.CharField("Ulice a číslo", max_length=255, blank=True)
    city = models.CharField("Město", max_length=120, blank=True)
    zip_code = models.CharField("PSČ", max_length=20, blank=True)
    country = models.CharField("Země", max_length=2, default="CZ", blank=True)

    # fakturační adresa
    invoice_name = models.CharField("Fakturační jméno / firma", max_length=255, blank=True)
    invoice_street = models.CharField("Fakturační ulice", max_length=255, blank=True)
    invoice_city = models.CharField("Fakturační město", max_length=120, blank=True)
    invoice_zip = models.CharField("Fakturační PSČ", max_length=20, blank=True)
    invoice_country = models.CharField("Fakturační země", max_length=2, default="CZ", blank=True)

    # oznámení a souhlasy
    marketing_consent = models.BooleanField(
        "Souhlas se zasíláním marketingových e-mailů", default=False
    )
    marketing_consent_updated_at = models.DateTimeField(
        "Souhlas aktualizován", null=True, blank=True
    )
    review_request_opt_in = models.BooleanField(
        "Žádost o recenzi po nákupu", default=True
    )

    class Meta:
        verbose_name = "Profil zákazníka"
        verbose_name_plural = "Profily zákazníků"

    def __str__(self):
        return f"Profil: {self.user.email}"

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        should_be_staff = self.is_admin_role or self.user.is_superuser
        if self.user.is_staff != should_be_staff:
            self.user.is_staff = should_be_staff
            self.user.save(update_fields=["is_staff"])
    

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        role = (
            UserProfile.Role.ADMIN
            if instance.is_staff or instance.is_superuser
            else UserProfile.Role.USER
        )
        UserProfile.objects.create(user=instance, role=role)


class Dog(models.Model):
    """Pes uživatele – údaje se předvyplní při rezervaci tréninku."""

    class Sex(models.TextChoices):
        MALE = "male", "Pes"
        FEMALE = "female", "Fena"

    class Neutered(models.TextChoices):
        YES = "yes", "Ano"
        NO = "no", "Ne"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dogs",
        verbose_name="Majitel",
    )
    name = models.CharField("Jméno psa", max_length=120)
    breed = models.CharField("Plemeno", max_length=160, blank=True)
    birth_date = models.DateField("Datum narození", null=True, blank=True)
    sex = models.CharField("Pohlaví", max_length=10, choices=Sex.choices, blank=True)
    is_neutered = models.CharField("Kastrace", max_length=3, choices=Neutered.choices, blank=True)
    weight = models.DecimalField("Hmotnost (kg)", max_digits=5, decimal_places=2, null=True, blank=True)
    color = models.CharField("Barva srsti", max_length=80, blank=True)
    chip_number = models.CharField("Číslo čipu / tetování", max_length=40, blank=True)
    vaccinated_on = models.DateField("Poslední očkování", null=True, blank=True)
    dewormed_on = models.DateField("Poslední odčervení", null=True, blank=True)
    diet = models.CharField("Dieta / krmení", max_length=255, blank=True)
    photo = models.ImageField(
        "Fotografie", upload_to="dogs/", blank=True, validators=[validate_photo_size]
    )
    notes = models.TextField("Poznámky", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pes"
        verbose_name_plural = "Psi"
        ordering = ["name"]

    def __str__(self):
        return self.name
