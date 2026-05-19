from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model


class UserProfile(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Uživatel"
        ADMIN = "admin", "Admin"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.USER,
    )

    phone = models.CharField(max_length=40, blank=True)

    # doručovací adresa
    street = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=2, default="CZ", blank=True)

    # fakturační adresa
    invoice_name = models.CharField(max_length=255, blank=True)
    invoice_street = models.CharField(max_length=255, blank=True)
    invoice_city = models.CharField(max_length=120, blank=True)
    invoice_zip = models.CharField(max_length=20, blank=True)
    invoice_country = models.CharField(max_length=2, default="CZ", blank=True)

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
