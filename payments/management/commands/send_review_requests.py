"""
Management command: send_review_requests
========================================
Odešle zákazníkům e-mail s žádostí o Google recenzi.

Spouštět automaticky přes Render cron job (každý den v 9:00).
Lze spustit i ručně: python manage.py send_review_requests

Kritéria pro odeslání:
  - Objednávka ve stavu PAID
  - paid_at je starší než REVIEW_DELAY_DAYS dní
  - review_request_sent_at je NULL (e-mail ještě nebyl odeslán)
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand
from django.utils import timezone

from payments.models import Order

logger = logging.getLogger(__name__)

# Počet dní po zaplacení, po kterých se odešle žádost o recenzi
REVIEW_DELAY_DAYS = getattr(settings, "REVIEW_DELAY_DAYS", 30)


class Command(BaseCommand):
    help = "Odešle e-maily se žádostí o Google recenzi zákazníkům 30 dní po nákupu."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Jen vypíše co by odeslal, ale neodešle e-maily ani neuloží do DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        review_url = getattr(settings, "GOOGLE_REVIEW_URL", "")
        from_email = settings.DEFAULT_FROM_EMAIL

        if not review_url:
            self.stderr.write(
                self.style.WARNING(
                    "GOOGLE_REVIEW_URL není nastaven v settings/env. "
                    "E-maily budou odeslány bez odkazu na recenzi."
                )
            )

        cutoff = timezone.now() - timedelta(days=REVIEW_DELAY_DAYS)

        orders = Order.objects.filter(
            status=Order.Status.PAID,
            paid_at__lte=cutoff,
            review_request_sent_at__isnull=True,
            buyer_email__gt="",  # musí mít e-mail
        ).select_related("user")

        count = orders.count()
        self.stdout.write(f"Nalezeno {count} objednávek ke zpracování.")

        sent = 0
        failed = 0

        for order in orders:
            if dry_run:
                self.stdout.write(
                    f"  [DRY RUN] Přeskakuji objednávku #{order.id} → {order.buyer_email}"
                )
                continue

            try:
                self._send_review_email(order, review_url, from_email)
                order.review_request_sent_at = timezone.now()
                order.save(update_fields=["review_request_sent_at"])
                sent += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Odesláno → {order.buyer_email} (objednávka #{order.id})")
                )
            except Exception as e:
                failed += 1
                logger.error(
                    f"[ReviewRequest] Nepodařilo se odeslat pro objednávku #{order.id}: {e}"
                )
                self.stderr.write(
                    self.style.ERROR(f"  ✗ Chyba → objednávka #{order.id}: {e}")
                )

        if not dry_run:
            self.stdout.write(f"\nHotovo: {sent} odesláno, {failed} chyb.")

    def _send_review_email(self, order, review_url, from_email):
        """Sestaví a odešle e-mail se žádostí o recenzi."""
        first_name = order.first_name or "zákazníku"

        review_section = (
            f"\n👉 Napsat recenzi na Google:\n{review_url}\n"
            if review_url
            else ""
        )

        body = f"""Dobrý den, {first_name},

před měsícem jste nakoupili u CalmDog a rádi bychom věděli, jak jste spokojeni.

Vaše zkušenost pomáhá dalším majitelům psů najít správnou pomoc. Pokud máte chvilku, budeme rádi za krátkou recenzi na Google:{review_section}
Stačí pár slov – hodně to znamená!

Děkujeme za důvěru,
Andrea & tým CalmDog
info@calmdog.cz
+420 608 163 824
"""

        email = EmailMessage(
            subject="Jak jste spokojeni s nákupem u CalmDog?",
            body=body,
            from_email=from_email,
            to=[order.buyer_email],
        )
        email.send(fail_silently=False)
