"""
Views rezervačního systému.

Rezervační flow (vše `@login_required`):
  my_reservations   – karta v profilu (budoucí rezervace + historie)
  select_location   – výběr města
  available_slots   – volné budoucí sloty pro město seskupené po dnech
  book_slot         – potvrzení a atomické vytvoření rezervace
  cancel_reservation– zrušení vlastní budoucí rezervace
  reservation_success – potvrzovací stránka

Google OAuth (admin, `@staff_member_required`):
  google_oauth_start / google_oauth_callback – jednorázové připojení trenéra.

Ochrana proti souběhu: rezervace se vytváří v `transaction.atomic()` nad
`select_for_update()` zamčeným slotem; Google událost a e-maily se řeší až
PO commitu, aby pomalé/chybující volání nedrželo zámek.
"""

import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import TrainingBookingForm
from .models import Location, Trainer, TrainingReservation, TrainingSlot
from .services import google_calendar, notifications

logger = logging.getLogger(__name__)


class SlotUnavailable(Exception):
    """Slot nelze rezervovat (mezitím obsazen / zablokován / v minulosti)."""


# ──────────────────────────────────────────────────────────
# Karta v profilu
# ──────────────────────────────────────────────────────────

@login_required
def my_reservations(request):
    # Kanonická karta „Rezervace tréninků" žije v profilu (accounts:reservations),
    # kam se propisují data z tohoto systému. Rezervační flow (potvrzení, zrušení,
    # „Zpět") směřuje sem, proto uživatele přesměrujeme na profilovou kartu.
    return redirect("accounts:reservations")


# ──────────────────────────────────────────────────────────
# Výběr města
# ──────────────────────────────────────────────────────────

@login_required
def select_location(request):
    locations = Location.objects.filter(is_active=True)
    return render(request, "trainings/select_location.html", {
        "account_section": "trainings",
        "locations": locations,
    })


# ──────────────────────────────────────────────────────────
# Volné termíny pro město
# ──────────────────────────────────────────────────────────

@login_required
def available_slots(request, slug):
    location = get_object_or_404(Location, slug=slug, is_active=True)
    now = timezone.now()

    slots = (
        TrainingSlot.objects.filter(
            location=location,
            status=TrainingSlot.Status.OPEN,
            window__is_active=True,
            start__gt=now,
        )
        .select_related("trainer", "window")
        .annotate(
            confirmed_count=Count(
                "reservations",
                filter=Q(reservations__status=TrainingReservation.Status.CONFIRMED),
            )
        )
        .order_by("start")
    )

    # Seskup volné (neobsazené) sloty po dnech
    days = []
    current = None
    for slot in slots:
        slot.calc_spots_left = max(slot.capacity - slot.confirmed_count, 0)
        if slot.calc_spots_left <= 0:
            continue
        slot_day = timezone.localtime(slot.start).date()
        if current is None or current["date"] != slot_day:
            current = {"date": slot_day, "slots": []}
            days.append(current)
        current["slots"].append(slot)

    return render(request, "trainings/available_slots.html", {
        "account_section": "trainings",
        "location": location,
        "days": days,
    })


# ──────────────────────────────────────────────────────────
# Rezervace slotu
# ──────────────────────────────────────────────────────────

def _create_reservation(user, slot, form):
    """Atomicky vytvoří rezervaci pod zámkem slotu. Vrací rezervaci nebo vyhodí SlotUnavailable."""
    with transaction.atomic():
        locked = (
            TrainingSlot.objects.select_for_update()
            .select_related("window")
            .get(pk=slot.pk)
        )

        if locked.status != TrainingSlot.Status.OPEN or not locked.window.is_active:
            raise SlotUnavailable("Tento termín byl mezitím zablokován.")
        if locked.start <= timezone.now():
            raise SlotUnavailable("Tento termín už proběhl.")

        confirmed = locked.reservations.filter(
            status=TrainingReservation.Status.CONFIRMED
        )
        if confirmed.filter(user=user).exists():
            raise SlotUnavailable("Tento termín už máš rezervovaný.")
        if confirmed.count() >= locked.capacity:
            raise SlotUnavailable("Tento termín je bohužel již plně obsazený.")

        reservation = form.save(commit=False)
        reservation.slot = locked
        reservation.user = user
        reservation.status = TrainingReservation.Status.CONFIRMED
        try:
            reservation.save()
        except IntegrityError:
            # Záložní pojistka k conditional unique constraintu (slot, user)
            raise SlotUnavailable("Tento termín už máš rezervovaný.")

    return reservation


def _finalize_booking(reservation):
    """Po commitu: vytvoř Google událost (uloží event_id) a rozešli e-maily."""
    event_id = google_calendar.create_event(reservation)
    if event_id:
        reservation.google_event_id = event_id
        reservation.save(update_fields=["google_event_id"])
    notifications.send_booking_emails(reservation)


@login_required
def book_slot(request, slot_id):
    slot = get_object_or_404(
        TrainingSlot.objects.select_related("location", "trainer", "window"),
        pk=slot_id,
    )

    if not slot.is_bookable:
        messages.error(request, "Tento termín už bohužel není dostupný.")
        return redirect("trainings:available_slots", slug=slot.location.slug)

    already = TrainingReservation.objects.filter(
        slot=slot, user=request.user, status=TrainingReservation.Status.CONFIRMED
    ).exists()
    if already:
        messages.info(request, "Tento termín už máš rezervovaný.")
        return redirect("trainings:my_reservations")

    if request.method == "POST":
        form = TrainingBookingForm(request.POST)
        if form.is_valid():
            try:
                reservation = _create_reservation(request.user, slot, form)
            except SlotUnavailable as exc:
                messages.error(request, str(exc))
                return redirect("trainings:available_slots", slug=slot.location.slug)
            _finalize_booking(reservation)
            messages.success(
                request,
                "Rezervace proběhla úspěšně. Potvrzení jsme ti poslali e-mailem.",
            )
            return redirect("trainings:reservation_success", pk=reservation.pk)
    else:
        profile = getattr(request.user, "profile", None)
        form = TrainingBookingForm(initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "email": request.user.email,
            "phone": getattr(profile, "phone", ""),
        })

    return render(request, "trainings/book_slot.html", {
        "account_section": "trainings",
        "slot": slot,
        "form": form,
    })


@login_required
def reservation_success(request, pk):
    reservation = get_object_or_404(
        TrainingReservation.objects.select_related(
            "slot", "slot__location", "slot__trainer"
        ),
        pk=pk,
        user=request.user,
    )
    return render(request, "trainings/reservation_success.html", {
        "account_section": "trainings",
        "reservation": reservation,
    })


# ──────────────────────────────────────────────────────────
# Zrušení rezervace
# ──────────────────────────────────────────────────────────

@login_required
@require_POST
def cancel_reservation(request, pk):
    reservation = get_object_or_404(
        TrainingReservation.objects.select_related(
            "slot", "slot__trainer", "slot__location"
        ),
        pk=pk,
        user=request.user,
    )

    if reservation.status == TrainingReservation.Status.CANCELED:
        messages.info(request, "Tato rezervace už byla zrušena.")
        return redirect("trainings:my_reservations")

    if not reservation.is_cancellable:
        messages.error(request, "Tuto rezervaci už nelze zrušit.")
        return redirect("trainings:my_reservations")

    reservation.status = TrainingReservation.Status.CANCELED
    reservation.canceled_at = timezone.now()
    reservation.save(update_fields=["status", "canceled_at"])

    # Kapacita se uvolní automaticky (počítáme jen CONFIRMED rezervace).
    google_calendar.delete_event(reservation)
    notifications.send_cancellation_emails(reservation)

    messages.success(request, "Rezervace byla zrušena.")
    return redirect("trainings:my_reservations")


# ──────────────────────────────────────────────────────────
# Google Calendar OAuth (admin)
# ──────────────────────────────────────────────────────────

@staff_member_required
def google_oauth_start(request, trainer_id):
    trainer = get_object_or_404(Trainer, pk=trainer_id)

    if not google_calendar.is_enabled():
        messages.error(
            request,
            "Google integrace není nakonfigurovaná (chybí OAuth klient v nastavení).",
        )
        return redirect("admin:trainings_trainer_change", trainer_id)

    flow = google_calendar.build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    request.session["gcal_oauth_state"] = state
    request.session["gcal_oauth_trainer"] = trainer.pk
    return redirect(auth_url)


@staff_member_required
def google_oauth_callback(request):
    state = request.session.get("gcal_oauth_state")
    trainer_id = request.session.get("gcal_oauth_trainer")

    if not state or not trainer_id:
        messages.error(request, "Chybí stav OAuth – zkuste připojení znovu.")
        return redirect("admin:trainings_trainer_changelist")

    trainer = get_object_or_404(Trainer, pk=trainer_id)

    flow = google_calendar.build_flow(state=state)
    try:
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        google_calendar.save_credentials(trainer, flow.credentials)
    except Exception as exc:
        logger.error(f"[GCal] OAuth callback selhal (trenér #{trainer_id}): {exc}")
        messages.error(request, f"Připojení Google kalendáře selhalo: {exc}")
        return redirect("admin:trainings_trainer_change", trainer_id)
    finally:
        request.session.pop("gcal_oauth_state", None)
        request.session.pop("gcal_oauth_trainer", None)

    messages.success(
        request, f"Google kalendář trenéra {trainer.name} byl úspěšně připojen."
    )
    return redirect("admin:trainings_trainer_change", trainer_id)
