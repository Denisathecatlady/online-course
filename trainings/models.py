"""
Modely rezervačního systému tréninků.

Návrh je záměrně rozšiřitelný:
  - Location  … lokality (Žatec, Náchod, … lze přidat další)
  - Trainer   … trenéři (více trenérů, každý s vlastním Google kalendářem)
  - AvailabilityWindow … časové okno, které trenér zadá v adminu
  - TrainingSlot        … materializovaný slot vygenerovaný z okna
  - TrainingReservation … konkrétní rezervace klienta (1 účastník)

Skupinové lekce: slot má kapacitu; obsazenost se počítá z počtu potvrzených
rezervací. Individuální lekce = kapacita 1.
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Location(models.Model):
    """Lokalita / město konání tréninků."""

    name = models.CharField("Město / lokalita", max_length=120)
    slug = models.SlugField("URL identifikátor", max_length=140, unique=True)
    address = models.CharField("Adresa", max_length=255, blank=True)
    is_active = models.BooleanField("Aktivní", default=True)
    order = models.PositiveSmallIntegerField("Pořadí", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Lokalita"
        verbose_name_plural = "Lokality"

    def __str__(self):
        return self.name


class Trainer(models.Model):
    """Trenér. Připraveno na více trenérů + napojení na Google kalendář přes OAuth."""

    name = models.CharField("Jméno trenéra", max_length=120)
    email = models.EmailField("E-mail trenéra")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trainer_profile",
        verbose_name="Uživatelský účet",
    )
    locations = models.ManyToManyField(
        Location,
        blank=True,
        related_name="trainers",
        verbose_name="Obsluhované lokality",
    )
    is_active = models.BooleanField("Aktivní", default=True)

    # ── Google Calendar (OAuth) ───────────────────────────────
    google_calendar_id = models.CharField(
        "ID Google kalendáře", max_length=255, default="primary", blank=True
    )
    google_oauth_token = models.TextField("Google OAuth token (JSON)", blank=True)
    google_connected = models.BooleanField("Google kalendář připojen", default=False)

    class Meta:
        ordering = ["name"]
        verbose_name = "Trenér"
        verbose_name_plural = "Trenéři"

    def __str__(self):
        return self.name

    @property
    def google_ready(self):
        """Lze pro tohoto trenéra volat Google Calendar API?"""
        return bool(self.google_connected and self.google_oauth_token)


class AvailabilityWindow(models.Model):
    """
    Časové okno, které trenér zadá v administraci. Systém ho rozdělí
    na jednotlivé rezervovatelné sloty (viz `generate_slots`).
    """

    class SessionType(models.TextChoices):
        INDIVIDUAL = "individual", "Individuální"
        GROUP = "group", "Skupinová"

    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="windows", verbose_name="Lokalita"
    )
    trainer = models.ForeignKey(
        Trainer, on_delete=models.PROTECT, related_name="windows", verbose_name="Trenér"
    )
    date = models.DateField("Datum")
    start_time = models.TimeField("Začátek")
    end_time = models.TimeField("Konec")
    slot_duration_minutes = models.PositiveSmallIntegerField("Délka slotu (min)", default=60)
    session_type = models.CharField(
        "Typ lekce", max_length=20, choices=SessionType.choices, default=SessionType.INDIVIDUAL
    )
    capacity = models.PositiveSmallIntegerField(
        "Kapacita slotu (počet účastníků)",
        default=1,
        help_text="Individuální = 1, skupinová = počet míst na jeden slot.",
    )
    is_active = models.BooleanField(
        "Aktivní",
        default=True,
        help_text="Odškrtnutím okno zablokujete (sloty se nenabízejí).",
    )
    note = models.CharField("Poznámka", max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "start_time"]
        verbose_name = "Časové okno"
        verbose_name_plural = "Časová okna"

    def __str__(self):
        return f"{self.location} – {self.date:%d.%m.%Y} {self.start_time:%H:%M}–{self.end_time:%H:%M}"

    # ── Validace ──────────────────────────────────────────────
    @staticmethod
    def _minutes(t):
        return t.hour * 60 + t.minute

    def clean(self):
        errors = {}

        # 1) Konec musí být po začátku
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            errors["end_time"] = "Konec musí být po začátku."

        # 2) Délka slotu se musí vejít do okna
        if self.start_time and self.end_time and self.slot_duration_minutes:
            window_minutes = self._minutes(self.end_time) - self._minutes(self.start_time)
            if window_minutes > 0 and self.slot_duration_minutes > window_minutes:
                errors["slot_duration_minutes"] = "Délka slotu je delší než celé okno."

        # 3) Kapacita alespoň 1
        if self.capacity is not None and self.capacity < 1:
            errors["capacity"] = "Kapacita musí být alespoň 1."

        # 4) Žádné překrývající se okno (stejná lokalita + trenér + datum)
        if all([self.location_id, self.trainer_id, self.date, self.start_time, self.end_time]):
            overlapping = AvailabilityWindow.objects.filter(
                location_id=self.location_id,
                trainer_id=self.trainer_id,
                date=self.date,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).exclude(pk=self.pk)
            if overlapping.exists():
                errors["__all__"] = (
                    "Toto okno se překrývá s jiným oknem stejného trenéra a lokality ve stejný den."
                )

        # 5) Guard: neměnit lokalitu/trenéra okna, které už má potvrzené rezervace
        if self.pk:
            has_confirmed = TrainingReservation.objects.filter(
                slot__window_id=self.pk,
                status=TrainingReservation.Status.CONFIRMED,
            ).exists()
            if has_confirmed:
                old = (
                    AvailabilityWindow.objects.filter(pk=self.pk)
                    .values("location_id", "trainer_id")
                    .first()
                )
                if old and (
                    old["location_id"] != self.location_id
                    or old["trainer_id"] != self.trainer_id
                ):
                    errors["__all__"] = (
                        "Nelze změnit lokalitu ani trenéra okna, které už má potvrzené rezervace."
                    )

        if errors:
            raise ValidationError(errors)

    # ── Generování slotů ──────────────────────────────────────
    def generate_slots(self):
        """
        Vygeneruje / doplní sloty pro toto okno. Aditivní a bezpečné:
          - nikdy nemaže ani neruší sloty s potvrzenou rezervací,
          - doplní chybějící sloty,
          - u volných slotů aktualizuje kapacitu/typ/konec,
          - volné sloty mimo aktuální hranice okna smaže.

        Vrací počet nově vytvořených slotů.
        """
        tz = timezone.get_current_timezone()

        # Cílové (start, end) dvojice v rámci okna
        targets = []
        cursor = datetime.combine(self.date, self.start_time)
        window_end = datetime.combine(self.date, self.end_time)
        step = timedelta(minutes=self.slot_duration_minutes)
        while cursor + step <= window_end:
            slot_start = timezone.make_aware(cursor, tz)
            slot_end = timezone.make_aware(cursor + step, tz)
            targets.append((slot_start, slot_end))
            cursor += step

        target_start_set = {s for s, _ in targets}
        existing = {slot.start: slot for slot in self.slots.all()}
        created = 0

        for slot_start, slot_end in targets:
            slot = existing.get(slot_start)
            if slot is None:
                TrainingSlot.objects.create(
                    window=self,
                    location=self.location,
                    trainer=self.trainer,
                    start=slot_start,
                    end=slot_end,
                    capacity=self.capacity,
                    session_type=self.session_type,
                )
                created += 1
            elif not slot.has_confirmed_reservations:
                # Volný slot – zaktualizuj podle okna
                slot.end = slot_end
                slot.capacity = self.capacity
                slot.session_type = self.session_type
                slot.location = self.location
                slot.trainer = self.trainer
                slot.save(
                    update_fields=["end", "capacity", "session_type", "location", "trainer"]
                )

        # Smaž volné sloty mimo aktuální hranice okna
        for start, slot in existing.items():
            if start not in target_start_set and not slot.has_confirmed_reservations:
                slot.delete()

        return created


class TrainingSlot(models.Model):
    """Materializovaný rezervovatelný slot vygenerovaný z časového okna."""

    class Status(models.TextChoices):
        OPEN = "open", "Volný"
        BLOCKED = "blocked", "Blokovaný"

    window = models.ForeignKey(
        AvailabilityWindow, on_delete=models.CASCADE, related_name="slots", verbose_name="Okno"
    )
    location = models.ForeignKey(
        Location, on_delete=models.PROTECT, related_name="slots", verbose_name="Lokalita"
    )
    trainer = models.ForeignKey(
        Trainer, on_delete=models.PROTECT, related_name="slots", verbose_name="Trenér"
    )
    start = models.DateTimeField("Začátek")
    end = models.DateTimeField("Konec")
    capacity = models.PositiveSmallIntegerField("Kapacita", default=1)
    session_type = models.CharField(
        "Typ lekce",
        max_length=20,
        choices=AvailabilityWindow.SessionType.choices,
        default=AvailabilityWindow.SessionType.INDIVIDUAL,
    )
    status = models.CharField("Stav", max_length=20, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["start"]
        verbose_name = "Slot"
        verbose_name_plural = "Sloty"
        constraints = [
            models.UniqueConstraint(fields=["trainer", "start"], name="uniq_trainer_slot_start"),
        ]

    def __str__(self):
        return f"{self.location} – {timezone.localtime(self.start):%d.%m.%Y %H:%M}"

    # ── Obsazenost ────────────────────────────────────────────
    @property
    def has_confirmed_reservations(self):
        return self.reservations.filter(status=TrainingReservation.Status.CONFIRMED).exists()

    @property
    def spots_taken(self):
        return self.reservations.filter(status=TrainingReservation.Status.CONFIRMED).count()

    @property
    def spots_left(self):
        return max(self.capacity - self.spots_taken, 0)

    @property
    def is_full(self):
        return self.spots_left <= 0

    @property
    def is_group(self):
        return self.session_type == AvailabilityWindow.SessionType.GROUP

    @property
    def is_past(self):
        return self.start <= timezone.now()

    @property
    def is_active_window(self):
        return self.window.is_active

    @property
    def is_bookable(self):
        return (
            self.status == self.Status.OPEN
            and self.is_active_window
            and not self.is_full
            and not self.is_past
        )


class TrainingReservation(models.Model):
    """Konkrétní rezervace klienta (jeden účastník = jedna rezervace)."""

    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Potvrzeno"
        CANCELED = "canceled", "Zrušeno"
        COMPLETED = "completed", "Absolvováno"

    slot = models.ForeignKey(
        TrainingSlot, on_delete=models.PROTECT, related_name="reservations", verbose_name="Slot"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="training_reservations",
        verbose_name="Uživatel",
    )

    # Snapshot kontaktu (kdyby se profil později změnil)
    first_name = models.CharField("Jméno", max_length=120)
    last_name = models.CharField("Příjmení", max_length=120)
    email = models.EmailField("E-mail")
    phone = models.CharField("Telefon", max_length=40, blank=True)
    dog_name = models.CharField("Jméno psa", max_length=120)
    note = models.TextField("Poznámka", blank=True)

    status = models.CharField(
        "Stav", max_length=20, choices=Status.choices, default=Status.CONFIRMED
    )
    google_event_id = models.CharField("ID Google události", max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    canceled_at = models.DateTimeField("Zrušeno dne", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Rezervace tréninku"
        verbose_name_plural = "Rezervace tréninků"
        constraints = [
            # Jeden uživatel nemůže mít 2 potvrzené rezervace na stejný slot.
            # Zrušené rezervace zůstávají (historie) a slot lze rezervovat znovu.
            models.UniqueConstraint(
                fields=["slot", "user"],
                condition=Q(status="confirmed"),
                name="uniq_active_slot_user",
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} – {self.slot}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def location(self):
        return self.slot.location

    @property
    def trainer(self):
        return self.slot.trainer

    @property
    def is_cancellable(self):
        return self.status == self.Status.CONFIRMED and self.slot.start > timezone.now()

    @property
    def is_upcoming(self):
        return self.status == self.Status.CONFIRMED and self.slot.start > timezone.now()

    @property
    def is_past(self):
        return self.slot.start <= timezone.now()
