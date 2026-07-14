"""
E-mailové notifikace k tréninkovým rezervacím.

Plain-text e-maily přes `django.core.mail.EmailMessage`, synchronně,
obalené v try/except s logováním – stejný vzor jako `hotel/views.py`.
Notifikace trenérovi jdou na e-mail konkrétního trenéra (`slot.trainer.email`).
"""

import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

logger = logging.getLogger(__name__)

SIGNATURE = """
S pozdravem,
CalmDog
info@calmdog.cz
+420 608 163 824
"""


def _details(reservation) -> dict:
    slot = reservation.slot
    start = timezone.localtime(slot.start)
    end = timezone.localtime(slot.end)
    return {
        "date": start.strftime("%d. %m. %Y"),
        "time": f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}",
        "location": slot.location.name,
        "type": "Skupinový trénink" if slot.is_group else "Individuální trénink",
    }


# ──────────────────────────────────────────────────────────
# Veřejné API
# ──────────────────────────────────────────────────────────

def send_booking_emails(reservation):
    _send_client_confirmation(reservation)
    _send_trainer_notification(reservation)


def send_cancellation_emails(reservation):
    _send_client_cancellation(reservation)
    _send_trainer_cancellation(reservation)


# ──────────────────────────────────────────────────────────
# Klient
# ──────────────────────────────────────────────────────────

def _send_client_confirmation(reservation):
    try:
        d = _details(reservation)
        body = f"""Dobrý den, {reservation.first_name},

potvrzujeme Vaši rezervaci tréninku v CalmDog.

  Typ:      {d['type']}
  Datum:    {d['date']}
  Čas:      {d['time']}
  Místo:    {d['location']}
  Pes:      {reservation.dog_name}
"""
        if reservation.note:
            body += f"  Poznámka: {reservation.note}\n"
        body += (
            "\nRezervaci najdete i ve svém profilu v sekci „Rezervace tréninků“,\n"
            "kde ji můžete případně zrušit.\n"
            + SIGNATURE
        )

        EmailMessage(
            subject="CalmDog – potvrzení rezervace tréninku",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[reservation.email],
        ).send()
    except Exception as e:
        logger.error(f"[Trainings] Chyba odeslání potvrzení klientovi (#{reservation.pk}): {e}")


def _send_client_cancellation(reservation):
    try:
        d = _details(reservation)
        body = f"""Dobrý den, {reservation.first_name},

Vaše rezervace tréninku byla zrušena.

  Typ:   {d['type']}
  Datum: {d['date']}
  Čas:   {d['time']}
  Místo: {d['location']}

Pokud budete mít zájem o nový termín, rádi Vás uvidíme.
{SIGNATURE}"""

        EmailMessage(
            subject="CalmDog – zrušení rezervace tréninku",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[reservation.email],
        ).send()
    except Exception as e:
        logger.error(f"[Trainings] Chyba odeslání zrušení klientovi (#{reservation.pk}): {e}")


# ──────────────────────────────────────────────────────────
# Trenér
# ──────────────────────────────────────────────────────────

def _trainer_email(reservation):
    return reservation.slot.trainer.email or settings.DEFAULT_FROM_EMAIL


def _send_trainer_notification(reservation):
    try:
        d = _details(reservation)
        body = f"""Nová rezervace tréninku!

  Typ:      {d['type']}
  Datum:    {d['date']}
  Čas:      {d['time']}
  Místo:    {d['location']}

Klient:   {reservation.full_name}
E-mail:   {reservation.email}
Telefon:  {reservation.phone or '–'}
Pes:      {reservation.dog_name}
"""
        if reservation.note:
            body += f"Poznámka: {reservation.note}\n"

        EmailMessage(
            subject=f"[Trénink] Nová rezervace – {reservation.full_name} ({d['date']} {d['time']})",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[_trainer_email(reservation)],
        ).send()
    except Exception as e:
        logger.error(f"[Trainings] Chyba notifikace trenérovi (#{reservation.pk}): {e}")


def _send_trainer_cancellation(reservation):
    try:
        d = _details(reservation)
        body = f"""Rezervace tréninku byla zrušena.

  Typ:      {d['type']}
  Datum:    {d['date']}
  Čas:      {d['time']}
  Místo:    {d['location']}

Klient:   {reservation.full_name}
E-mail:   {reservation.email}
Telefon:  {reservation.phone or '–'}
Pes:      {reservation.dog_name}
"""
        EmailMessage(
            subject=f"[Trénink] Zrušená rezervace – {reservation.full_name} ({d['date']} {d['time']})",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[_trainer_email(reservation)],
        ).send()
    except Exception as e:
        logger.error(f"[Trainings] Chyba notifikace o zrušení trenérovi (#{reservation.pk}): {e}")
