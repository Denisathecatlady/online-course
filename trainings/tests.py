"""
Testy rezervačního systému tréninků.

Pokrývají automatické kontroly ze zadání:
  - generování slotů (počet, konfigurovatelná délka, aditivní edit nemaže booked),
  - zákaz překrývajících se oken,
  - kapacita / plný slot (individuální i skupinový),
  - zákaz rezervace v minulosti,
  - zákaz dvojité rezervace stejného slotu stejným uživatelem,
  - zrušení uvolní kapacitu + je idempotentní,
  - notifikační e-maily.
"""

from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    AvailabilityWindow,
    Location,
    TrainingReservation,
    TrainingSlot,
    Trainer,
)

User = get_user_model()


def future_date(days=7):
    return (timezone.localtime() + timedelta(days=days)).date()


class SlotGenerationTests(TestCase):
    def setUp(self):
        self.location = Location.objects.create(name="Žatec", slug="zatec")
        self.trainer = Trainer.objects.create(name="Trenér", email="t@example.com")

    def _window(self, **kwargs):
        defaults = dict(
            location=self.location,
            trainer=self.trainer,
            date=future_date(),
            start_time=time(9, 0),
            end_time=time(12, 0),
            slot_duration_minutes=60,
        )
        defaults.update(kwargs)
        return AvailabilityWindow.objects.create(**defaults)

    def test_generates_expected_number_of_slots(self):
        window = self._window()
        created = window.generate_slots()
        self.assertEqual(created, 3)
        self.assertEqual(window.slots.count(), 3)

    def test_slot_duration_is_configurable(self):
        window = self._window(
            start_time=time(9, 0), end_time=time(10, 30), slot_duration_minutes=30
        )
        window.generate_slots()
        # 9:00–9:30, 9:30–10:00, 10:00–10:30
        self.assertEqual(window.slots.count(), 3)

    def test_group_capacity_copied_to_slots(self):
        window = self._window(
            session_type=AvailabilityWindow.SessionType.GROUP, capacity=4
        )
        window.generate_slots()
        self.assertTrue(all(s.capacity == 4 for s in window.slots.all()))

    def test_regeneration_preserves_booked_slot_out_of_bounds(self):
        window = self._window()  # 9–12 → 3 sloty
        window.generate_slots()
        last_slot = window.slots.order_by("start").last()  # 11:00–12:00
        user = User.objects.create_user(username="u", email="u@x.cz", password="p")
        TrainingReservation.objects.create(
            slot=last_slot, user=user, first_name="A", last_name="B",
            email="u@x.cz", dog_name="Rex",
        )
        # Zkrátíme okno tak, že poslední (booked) slot je mimo hranice.
        window.end_time = time(11, 0)
        window.save(update_fields=["end_time"])
        window.generate_slots()
        self.assertTrue(TrainingSlot.objects.filter(pk=last_slot.pk).exists())

    def test_regeneration_deletes_free_slots_out_of_bounds(self):
        window = self._window()  # 3 sloty
        window.generate_slots()
        window.end_time = time(11, 0)  # → jen 2 sloty
        window.save(update_fields=["end_time"])
        window.generate_slots()
        self.assertEqual(window.slots.count(), 2)


class WindowValidationTests(TestCase):
    def setUp(self):
        self.location = Location.objects.create(name="Náchod", slug="nachod")
        self.trainer = Trainer.objects.create(name="Trenér", email="t@example.com")

    def test_end_before_start_rejected(self):
        window = AvailabilityWindow(
            location=self.location, trainer=self.trainer, date=future_date(),
            start_time=time(12, 0), end_time=time(9, 0), slot_duration_minutes=60,
        )
        with self.assertRaises(ValidationError):
            window.full_clean()

    def test_slot_longer_than_window_rejected(self):
        window = AvailabilityWindow(
            location=self.location, trainer=self.trainer, date=future_date(),
            start_time=time(9, 0), end_time=time(10, 0), slot_duration_minutes=120,
        )
        with self.assertRaises(ValidationError):
            window.full_clean()

    def test_overlapping_window_rejected(self):
        AvailabilityWindow.objects.create(
            location=self.location, trainer=self.trainer, date=future_date(),
            start_time=time(9, 0), end_time=time(12, 0), slot_duration_minutes=60,
        )
        overlapping = AvailabilityWindow(
            location=self.location, trainer=self.trainer, date=future_date(),
            start_time=time(11, 0), end_time=time(13, 0), slot_duration_minutes=60,
        )
        with self.assertRaises(ValidationError):
            overlapping.full_clean()

    def test_adjacent_window_allowed(self):
        AvailabilityWindow.objects.create(
            location=self.location, trainer=self.trainer, date=future_date(),
            start_time=time(9, 0), end_time=time(12, 0), slot_duration_minutes=60,
        )
        adjacent = AvailabilityWindow(
            location=self.location, trainer=self.trainer, date=future_date(),
            start_time=time(12, 0), end_time=time(14, 0), slot_duration_minutes=60,
        )
        # Nemělo by vyhodit ValidationError kvůli překryvu.
        adjacent.full_clean()


class BookingFlowTests(TestCase):
    def setUp(self):
        self.location = Location.objects.create(name="Žatec", slug="zatec")
        self.trainer = Trainer.objects.create(name="Trenér", email="trener@example.com")
        self.window = AvailabilityWindow.objects.create(
            location=self.location, trainer=self.trainer, date=future_date(),
            start_time=time(9, 0), end_time=time(12, 0), slot_duration_minutes=60,
        )
        self.window.generate_slots()
        self.slot = self.window.slots.order_by("start").first()
        self.user = User.objects.create_user(
            username="klient", email="klient@x.cz", password="pw"
        )
        self.client.force_login(self.user)

    def _book(self, slot=None, **extra):
        slot = slot or self.slot
        data = {
            "first_name": "Jan", "last_name": "Novák", "email": "jan@x.cz",
            "phone": "", "dog_name": "Rex", "note": "",
        }
        data.update(extra)
        return self.client.post(reverse("trainings:book_slot", args=[slot.id]), data)

    def test_successful_booking_creates_reservation_and_sends_emails(self):
        resp = self._book()
        self.assertEqual(TrainingReservation.objects.count(), 1)
        reservation = TrainingReservation.objects.first()
        self.assertEqual(reservation.status, TrainingReservation.Status.CONFIRMED)
        self.assertRedirects(
            resp,
            reverse("trainings:reservation_success", args=[reservation.pk]),
            fetch_redirect_response=False,
        )
        # Klient + trenér
        self.assertEqual(len(mail.outbox), 2)

    def test_slot_disappears_after_individual_booking(self):
        self._book()
        self.slot.refresh_from_db()
        self.assertTrue(self.slot.is_full)
        self.assertFalse(self.slot.is_bookable)

    def test_same_user_cannot_double_book(self):
        self._book()
        self._book()  # znovu stejný slot
        self.assertEqual(
            TrainingReservation.objects.filter(
                slot=self.slot, status=TrainingReservation.Status.CONFIRMED
            ).count(),
            1,
        )

    def test_second_user_cannot_book_full_individual_slot(self):
        self._book()
        other = User.objects.create_user(username="other", email="o@x.cz", password="pw")
        self.client.force_login(other)
        self._book(email="other@x.cz")
        self.assertEqual(
            TrainingReservation.objects.filter(
                slot=self.slot, status=TrainingReservation.Status.CONFIRMED
            ).count(),
            1,
        )

    def test_group_slot_allows_multiple_up_to_capacity(self):
        gwindow = AvailabilityWindow.objects.create(
            location=self.location, trainer=self.trainer, date=future_date(3),
            start_time=time(14, 0), end_time=time(15, 0), slot_duration_minutes=60,
            session_type=AvailabilityWindow.SessionType.GROUP, capacity=2,
        )
        gwindow.generate_slots()
        gslot = gwindow.slots.first()

        u2 = User.objects.create_user(username="u2", email="u2@x.cz", password="pw")
        u3 = User.objects.create_user(username="u3", email="u3@x.cz", password="pw")

        self._book(slot=gslot, email="a@x.cz")  # user 1
        self.client.force_login(u2)
        self._book(slot=gslot, email="b@x.cz")  # user 2 → plno
        self.assertEqual(
            gslot.reservations.filter(status=TrainingReservation.Status.CONFIRMED).count(), 2
        )

        self.client.force_login(u3)
        self._book(slot=gslot, email="c@x.cz")  # user 3 → odmítnuto
        self.assertEqual(
            gslot.reservations.filter(status=TrainingReservation.Status.CONFIRMED).count(), 2
        )

    def test_cannot_book_slot_in_the_past(self):
        past_slot = TrainingSlot.objects.create(
            window=self.window, location=self.location, trainer=self.trainer,
            start=timezone.now() - timedelta(hours=2),
            end=timezone.now() - timedelta(hours=1), capacity=1,
        )
        self._book(slot=past_slot)
        self.assertEqual(
            TrainingReservation.objects.filter(slot=past_slot).count(), 0
        )

    def test_cancel_frees_capacity_and_is_idempotent(self):
        self._book()
        reservation = TrainingReservation.objects.get()
        cancel_url = reverse("trainings:cancel_reservation", args=[reservation.pk])

        mail.outbox.clear()
        self.client.post(cancel_url)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, TrainingReservation.Status.CANCELED)
        self.assertIsNotNone(reservation.canceled_at)
        self.assertEqual(len(mail.outbox), 2)  # klient + trenér o zrušení

        self.slot.refresh_from_db()
        self.assertTrue(self.slot.is_bookable)  # místo se uvolnilo

        # Druhé zrušení nic nezmění (idempotence) ani nepošle další e-maily.
        mail.outbox.clear()
        self.client.post(cancel_url)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, TrainingReservation.Status.CANCELED)
        self.assertEqual(len(mail.outbox), 0)

    def test_cancel_only_allowed_for_owner(self):
        self._book()
        reservation = TrainingReservation.objects.get()
        intruder = User.objects.create_user(username="zloduch", email="z@x.cz", password="pw")
        self.client.force_login(intruder)
        resp = self.client.post(
            reverse("trainings:cancel_reservation", args=[reservation.pk])
        )
        self.assertEqual(resp.status_code, 404)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, TrainingReservation.Status.CONFIRMED)

    def test_login_required(self):
        self.client.logout()
        resp = self.client.get(reverse("trainings:my_reservations"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)
        self.assertIn("next=/moje-treninky/", resp.url)
