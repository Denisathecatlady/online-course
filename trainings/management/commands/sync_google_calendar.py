"""
Management command: sync_google_calendar
========================================
Jednosměrná zpětná synchronizace z Google kalendáře do aplikace.

Projde budoucí POTVRZENÉ rezervace, které mají Google událost, a ověří, zda
událost v kalendáři trenéra stále existuje. Pokud byla v Googlu smazána,
zruší se odpovídající rezervace i v aplikaci (uvolní se místo, klientovi
i trenérovi odejde e-mail o zrušení).

Command NIKDY nevytváří události → nemůže vzniknout smyčka. App-side zrušení
nastavuje CANCELED dřív, než maže Google událost, takže sync ho už neřeší.

Spouštět přes Render cron (např. každých 30 min).
Ručně: python manage.py sync_google_calendar [--dry-run]
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from trainings.models import TrainingReservation
from trainings.services import google_calendar, notifications

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Zruší v aplikaci rezervace, jejichž událost byla smazána v Google kalendáři."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Jen vypíše, co by zrušil, ale nic nezmění ani neodešle.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if not google_calendar.is_enabled():
            self.stdout.write(
                self.style.WARNING("Google integrace je vypnutá – není co synchronizovat.")
            )
            return

        now = timezone.now()
        reservations = (
            TrainingReservation.objects.filter(
                status=TrainingReservation.Status.CONFIRMED,
                slot__start__gt=now,
            )
            .exclude(google_event_id="")
            .select_related("slot", "slot__trainer", "slot__location")
        )

        total = reservations.count()
        self.stdout.write(f"Kontroluji {total} budoucích rezervací s Google událostí.")

        canceled = 0
        skipped = 0

        for reservation in reservations:
            exists = google_calendar.event_exists(reservation)

            if exists is None:
                # Nelze zjistit (chyba API / trenér odpojen) → raději nechat být.
                skipped += 1
                continue
            if exists:
                continue

            # Událost v Googlu zmizela → zruš rezervaci i v aplikaci.
            if dry_run:
                self.stdout.write(
                    f"  [DRY RUN] Zrušil bych rezervaci #{reservation.pk} "
                    f"({reservation.full_name}, {reservation.slot})"
                )
                canceled += 1
                continue

            reservation.status = TrainingReservation.Status.CANCELED
            reservation.canceled_at = timezone.now()
            reservation.save(update_fields=["status", "canceled_at"])
            try:
                notifications.send_cancellation_emails(reservation)
            except Exception as exc:
                logger.error(
                    f"[GCalSync] Chyba e-mailu o zrušení (#{reservation.pk}): {exc}"
                )
            canceled += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Zrušena rezervace #{reservation.pk} ({reservation.full_name})"
                )
            )

        if dry_run:
            self.stdout.write(f"\n[DRY RUN] Ke zrušení: {canceled}, přeskočeno: {skipped}.")
        else:
            self.stdout.write(
                f"\nHotovo: zrušeno {canceled} rezervací, přeskočeno {skipped}."
            )
