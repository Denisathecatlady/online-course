from django.db import models


class HotelReservation(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Čeká na potvrzení"
        CONFIRMED = "confirmed", "Potvrzeno"
        CANCELED = "canceled", "Zrušeno"

    class PetType(models.TextChoices):
        DOG = "dog", "Pes"
        CAT = "cat", "Kočka"
        OTHER = "other", "Jiné"

    # Kontakt
    first_name = models.CharField("Jméno", max_length=120)
    last_name = models.CharField("Příjmení", max_length=120)
    email = models.EmailField("E-mail")
    phone = models.CharField("Telefon", max_length=40, blank=True)

    # Termín
    date_from = models.DateField("Datum příjezdu")
    date_to = models.DateField("Datum odjezdu")

    # Zvíře
    pet_type = models.CharField("Druh zvířete", max_length=10, choices=PetType.choices, default=PetType.DOG)
    pet_count = models.PositiveSmallIntegerField("Počet zvířat", default=1)
    pet_name = models.CharField("Jméno zvířete", max_length=100, blank=True)
    pet_breed = models.CharField("Plemeno", max_length=100, blank=True)
    is_aggressive = models.BooleanField("Projevuje agresivní chování", default=False)
    aggression_notes = models.TextField("Popis chování", blank=True)

    # Poznámka
    notes = models.TextField("Další poznámky / speciální požadavky", blank=True)

    # Status
    status = models.CharField(
        "Stav",
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Rezervace hotelu"
        verbose_name_plural = "Rezervace hotelu"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.date_from} – {self.date_to})"

    @property
    def nights(self):
        return max((self.date_to - self.date_from).days, 0)
