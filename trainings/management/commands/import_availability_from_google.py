"""
Management command: import_availability_from_google
====================================================
Import volných termínů z dedikovaných Google kalendářů (jeden kalendář na
lokalitu, model `AvailabilityCalendar`) do aplikace.

Z každé události vznikne / aktualizuje se `AvailabilityWindow`, které se
rozdělí na rezervovatelné sloty. Idempotentní – opakovaný běh nevytváří
duplikáty (páruje se přes `google_event_id`). Události smazané v Googlu
deaktivují odpovídající okno a uvolní jeho volné sloty (potvrzené rezervace
zůstávají).

Spouštět přes Render cron (např. každých 15–30 min).
Ručně: python manage.py import_availability_from_google [--dry-run] [--days N]
"""

from django.core.management.base import BaseCommand

from trainings.services import availability_import, google_calendar


class Command(BaseCommand):
    help = "Naimportuje volné termíny z Google kalendářů dostupnosti do aplikace."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Jen vypíše, co by naimportoval, ale nic nezmění.",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Horizont importu ve dnech (výchozí dle TRAININGS_IMPORT_HORIZON_DAYS).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        days = options["days"]

        if not google_calendar.is_enabled():
            self.stdout.write(
                self.style.WARNING("Google integrace je vypnutá – není z čeho importovat.")
            )
            return

        stats = availability_import.import_from_google(horizon_days=days, dry_run=dry_run)

        prefix = "[DRY RUN] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Hotovo. Kalendářů: {stats['calendars']}, "
                f"vytvořeno: {stats['created']}, aktualizováno: {stats['updated']}, "
                f"deaktivováno: {stats['deactivated']}, přeskočeno: {stats['skipped']}."
            )
        )
