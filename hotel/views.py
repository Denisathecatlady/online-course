import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .forms import HotelReservationForm
from .models import HotelReservation
from .services.calendar import get_available_date_strings

logger = logging.getLogger(__name__)


# ===================================================
# POMOCNÉ FUNKCE
# ===================================================

def _get_booked_dates():
    """Vrátí set datumů, které jsou již obsazeny (pending nebo confirmed)."""
    booked = set()
    reservations = HotelReservation.objects.filter(
        status__in=[HotelReservation.Status.PENDING, HotelReservation.Status.CONFIRMED]
    ).values("date_from", "date_to")

    for r in reservations:
        current = r["date_from"]
        while current < r["date_to"]:
            booked.add(current)
            current += timedelta(days=1)

    return booked


def _send_customer_email(reservation):
    try:
        body = f"""Dobrý den, {reservation.first_name} {reservation.last_name},

děkujeme za Vaši poptávku hlídání v CalmDog Hotelu pro psy a kočky.

Přijatá rezervace:
  Termín:     {reservation.date_from.strftime("%d. %m. %Y")} – {reservation.date_to.strftime("%d. %m. %Y")} ({reservation.nights} nocí)
  Zvíře:      {reservation.get_pet_type_display()}, {reservation.pet_count} ks
  Jméno:      {reservation.pet_name or "–"}
  Plemeno:    {reservation.pet_breed or "–"}
"""
        if reservation.is_aggressive:
            body += f"  Poznámka ke chování: {reservation.aggression_notes or '–'}\n"

        if reservation.notes:
            body += f"  Další požadavky: {reservation.notes}\n"

        body += """
Vaši rezervaci zpracujeme a co nejdříve Vás kontaktujeme s potvrzením.

S pozdravem,
CalmDog Hotel
info@calmdog.cz
+420 608 163 824
"""
        email = EmailMessage(
            subject="CalmDog Hotel – přijali jsme Vaši poptávku",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[reservation.email],
        )
        email.send()
    except Exception as e:
        logger.error(f"Failed to send customer hotel email: {e}")


def _send_admin_notification(reservation):
    try:
        body = f"""Nová rezervace CalmDog Hotelu!

Zákazník:   {reservation.first_name} {reservation.last_name}
E-mail:     {reservation.email}
Telefon:    {reservation.phone or "–"}

Termín:     {reservation.date_from.strftime("%d. %m. %Y")} – {reservation.date_to.strftime("%d. %m. %Y")} ({reservation.nights} nocí)
Zvíře:      {reservation.get_pet_type_display()}, {reservation.pet_count} ks
Jméno:      {reservation.pet_name or "–"}
Plemeno:    {reservation.pet_breed or "–"}
Agresivní:  {"ANO ⚠️" if reservation.is_aggressive else "ne"}
"""
        if reservation.is_aggressive and reservation.aggression_notes:
            body += f"Popis chování: {reservation.aggression_notes}\n"

        if reservation.notes:
            body += f"\nPoznámka: {reservation.notes}\n"

        email = EmailMessage(
            subject=f"[Hotel] Nová rezervace – {reservation.first_name} {reservation.last_name} ({reservation.date_from.strftime('%d.%m.')} – {reservation.date_to.strftime('%d.%m.%Y')})",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.DEFAULT_FROM_EMAIL],
        )
        email.send()
    except Exception as e:
        logger.error(f"Failed to send admin hotel notification: {e}")


# ===================================================
# VIEWS
# ===================================================

@require_GET
def hotel_home(request):
    return render(request, "hotel/home.html")


@require_GET
def available_dates_json(request):
    """JSON endpoint – vrátí seznam volných datumů pro flatpickr."""
    ical_url = getattr(settings, "HOTEL_ICAL_URL", "").strip()

    if not ical_url:
        return JsonResponse({"available_dates": [], "calendar_configured": False})

    booked = _get_booked_dates()
    available = get_available_date_strings(ical_url, booked)

    return JsonResponse({"available_dates": available, "calendar_configured": True})


@require_http_methods(["GET", "POST"])
def reservation_form(request):
    ical_url = getattr(settings, "HOTEL_ICAL_URL", "").strip()
    has_calendar = bool(ical_url)

    if request.method == "POST":
        form = HotelReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save()
            _send_customer_email(reservation)
            _send_admin_notification(reservation)
            return redirect("hotel:reservation_success")
    else:
        form = HotelReservationForm()

    return render(request, "hotel/reservation_form.html", {
        "form": form,
        "has_calendar": has_calendar,
    })


@require_GET
def reservation_success(request):
    return render(request, "hotel/reservation_success.html")
