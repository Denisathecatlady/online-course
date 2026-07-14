"""
Import volných termínů z Google kalendáře → AvailabilityWindow → sloty.

Trenér kreslí okna dostupnosti do dedikovaného Google kalendáře pro každou
lokalitu (viz model `AvailabilityCalendar`). Tato služba události přečte a
namapuje na `AvailabilityWindow`, které se pak stávajícím `generate_slots()`
rozdělí na rezervovatelné `TrainingSlot`. Zobrazení uživatelům
(`available_slots.html`) tím funguje beze změny.

Vlastnosti:
  - Idempotentní: okna se párují přes `google_event_id`, opakovaný běh
    aktualizuje, nevytváří duplikáty.
  - Bezpečné: nikdy neruší potvrzené rezervace ani jejich sloty; smazané
    události v Googlu jen deaktivují okno a odeberou VOLNÉ sloty.
  - Odolné: každá událost je v try/except, chyba jedné nezruší celý import.

Typ lekce se určuje z názvu události: „skupina N" → skupinová (kapacita N),
jinak individuální (kapacita 1).
"""

import logging
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta

from trainings.models import AvailabilityCalendar, AvailabilityWindow
from trainings.services import google_calendar

logger = logging.getLogger(__name__)

# Výchozí kapacita skupinové lekce, když v názvu není uvedené číslo.
DEFAULT_GROUP_CAPACITY = 6

# „skupina", „skupinová", „skupinovka" … volitelně následované číslem kapacity.
_GROUP_RE = re.compile(r"skupin\w*\s*(\d+)?", re.IGNORECASE)


def parse_session_type(summary: str):
    """
    Z názvu události odvodí (session_type, capacity).

      "Skupina 5"      → ("group", 5)
      "skupinová"      → ("group", DEFAULT_GROUP_CAPACITY)
      "Individuální"   → ("individual", 1)
      cokoli jiného    → ("individual", 1)
    """
    match = _GROUP_RE.search(summary or "")
    if match:
        number = match.group(1)
        capacity = int(number) if number else DEFAULT_GROUP_CAPACITY
        capacity = max(capacity, 1)
        return AvailabilityWindow.SessionType.GROUP, capacity
    return AvailabilityWindow.SessionType.INDIVIDUAL, 1


def _horizon_days(explicit=None) -> int:
    if explicit:
        return int(explicit)
    return int(getattr(settings, "TRAININGS_IMPORT_HORIZON_DAYS", 60))


def import_from_google(horizon_days=None, dry_run=False) -> dict:
    """
    Projde všechny aktivní `AvailabilityCalendar` a naimportuje z nich okna.

    Vrací statistiky:
        {"created": int, "updated": int, "deactivated": int, "skipped": int,
         "calendars": int}
    """
    stats = {"created": 0, "updated": 0, "deactivated": 0, "skipped": 0, "calendars": 0}

    if not google_calendar.is_enabled():
        logger.info("[Import] Google integrace vypnutá – není z čeho importovat.")
        return stats

    now = timezone.now()
    horizon = _horizon_days(horizon_days)
    time_max = now + timedelta(days=horizon)
    today = timezone.localdate(now)
    horizon_date = timezone.localdate(time_max)

    calendars = (
        AvailabilityCalendar.objects.filter(is_active=True, trainer__is_active=True)
        .select_related("trainer", "location")
    )

    for cal in calendars:
        if not cal.trainer.google_ready:
            logger.info(f"[Import] Trenér {cal.trainer} nepřipojen – přeskakuji {cal}.")
            continue

        stats["calendars"] += 1
        events = google_calendar.list_events(
            cal.trainer, cal.google_calendar_id, now, time_max
        )
        seen_event_ids = set()

        for event in events:
            outcome = _import_event(cal, event, dry_run)
            if outcome in ("created", "updated"):
                seen_event_ids.add(event["event_id"])
            if outcome:
                stats[outcome] = stats.get(outcome, 0) + 1

        # Okna z Googlu pro tuto lokalitu, jejichž událost už v kalendáři není.
        stale = AvailabilityWindow.objects.filter(
            trainer=cal.trainer,
            location=cal.location,
            source=AvailabilityWindow.Source.GOOGLE,
            is_active=True,
            date__gte=today,
            date__lte=horizon_date,
        ).exclude(google_event_id__in=seen_event_ids)

        for window in stale:
            if dry_run:
                logger.info(f"[Import][DRY] Deaktivoval bych okno {window} (událost smazána).")
                stats["deactivated"] += 1
                continue
            _deactivate_window(window)
            stats["deactivated"] += 1

    return stats


def _import_event(cal, event, dry_run) -> str:
    """
    Zpracuje jednu událost. Vrací "created" / "updated" / "skipped" / "".
    """
    # Přeskoč celodenní, zrušené a události bez času.
    if event["all_day"] or event["status"] == "cancelled":
        return "skipped"
    if not event["start_dt"] or not event["end_dt"] or not event["event_id"]:
        return "skipped"

    start_local = timezone.localtime(event["start_dt"])
    end_local = timezone.localtime(event["end_dt"])

    # AvailabilityWindow je jednodenní → přeskoč události přes půlnoc / neplatné.
    if start_local.date() != end_local.date() or end_local <= start_local:
        logger.info(
            f"[Import] Přeskakuji událost {event['event_id']} "
            f"(celodenní/přes půlnoc/neplatná)."
        )
        return "skipped"

    session_type, capacity = parse_session_type(event["summary"])

    if dry_run:
        logger.info(
            f"[Import][DRY] {cal.location} {start_local:%d.%m. %H:%M}–{end_local:%H:%M} "
            f"({session_type}, kap. {capacity})."
        )
        # V suchém běhu nevíme, zda by šlo o created/updated – hlásíme jako updated,
        # aby se okno nepovažovalo za smazané.
        return "updated"

    try:
        window = AvailabilityWindow.objects.get(
            trainer=cal.trainer, google_event_id=event["event_id"]
        )
        created = False
    except AvailabilityWindow.DoesNotExist:
        window = AvailabilityWindow(
            trainer=cal.trainer, google_event_id=event["event_id"]
        )
        created = True

    window.location = cal.location
    window.date = start_local.date()
    window.start_time = start_local.time()
    window.end_time = end_local.time()
    window.slot_duration_minutes = cal.default_slot_minutes
    window.session_type = session_type
    window.capacity = capacity
    window.source = AvailabilityWindow.Source.GOOGLE
    window.is_active = True
    window.note = event["summary"][:255]

    try:
        with transaction.atomic():
            window.full_clean()  # kontrola překryvů (AvailabilityWindow.clean)
            window.save()
            window.generate_slots()
    except (ValidationError, IntegrityError) as e:
        logger.warning(
            f"[Import] Událost {event['event_id']} přeskočena (kolize/validace): {e}"
        )
        return "skipped"

    return "created" if created else "updated"


def _deactivate_window(window) -> None:
    """
    Deaktivuje okno, jehož zdrojová událost byla v Googlu smazána. Odebere jen
    sloty BEZ jakékoli rezervace; sloty, na kterých rezervace visí (i zrušená),
    zůstanou zachované – jednak kvůli `on_delete=PROTECT` na rezervaci, jednak
    aby se nezrušila existující rezervace klienta. Deaktivované okno se stejně
    v nabídce slotů nezobrazuje (view filtruje `window__is_active=True`).
    """
    with transaction.atomic():
        window.is_active = False
        window.save(update_fields=["is_active"])
        free_slots = window.slots.filter(reservations__isnull=True)
        deleted = free_slots.count()
        free_slots.delete()

    logger.info(f"[Import] Okno {window} deaktivováno, odebráno {deleted} volných slotů.")
