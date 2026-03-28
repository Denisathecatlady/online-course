from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile"
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
    

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)