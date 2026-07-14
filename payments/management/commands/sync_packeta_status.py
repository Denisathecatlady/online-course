"""
Management command: sync_packeta_status
========================================
Zeptá se Packety na aktuální stav zásilky (packetStatus) u zaplacených objednávek
a promítne ho do zjednodušeného stavu Order.shipping_status (Zpracovává se /
Odesláno / Doručeno). Packeta nemá webhook, takže se stav musí pravidelně dotazovat.

Spouštět automaticky přes Render cron job (každých ~30 minut).
Lze spustit i ručně: python manage.py sync_packeta_status

Mapování Packeta stavu na shipping_status je založené na klíčových slovech
v code_text/name (přesná číselná tabulka stavů nebyla z dokumentace dostupná).
Syrová data (packeta_last_status_code/name) se ukládají vždy, aby šlo mapování
podle reálného provozu doladit.
"""

import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from payments.models import Order
from payments.services.packeta import PacketaError, get_packet_status

logger = logging.getLogger(__name__)

# Klíčová slova (malými písmeny) hledaná v code_text/name odpovědi packetStatus.
#
# Pozor na české tvary: "vyzvednut(o/a)" (dokonáno – DORUČENO) vs. "k vyzvednutí"/
# "připraveno" (balík čeká na pobočce, NENÍ vyzvednutý – pořád jen ODESLÁNO).
# Stejně "doručeno" (hotovo) vs. "k doručení"/"doručuje se" (probíhá). Proto se
# nejdřív kontrolují tyto "čeká na vyzvednutí/doručení" fráze (mají přednost),
# a teprve pak širší "vyzvednut"/"doruč" znamenající DORUČENO.
PENDING_PICKUP_KEYWORDS = (
    "k vyzvednutí", "na vyzvednutí", "čeká na", "připraven",
    "k doručení", "doručuje se", "ready for pickup", "ready to be", "awaiting",
)
DELIVERED_KEYWORDS = ("deliver", "doruč", "vyzvednut", "collected", "picked up")
SHIPPED_KEYWORDS = ("dispatch", "carrier", "expedic", "přeprav", "cest", "handed", "předá", "transit")


def _parse_date(value):
    """Zkusí naparsovat datum/čas z Packety (ISO 8601, např. 2025-06-30T11:28:59); jinak None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)


def _map_status(code_text, name):
    text = f"{code_text or ''} {name or ''}".lower()
    if any(kw in text for kw in PENDING_PICKUP_KEYWORDS):
        return Order.ShippingStatus.SHIPPED
    if any(kw in text for kw in DELIVERED_KEYWORDS):
        return Order.ShippingStatus.DELIVERED
    if any(kw in text for kw in SHIPPED_KEYWORDS):
        return Order.ShippingStatus.SHIPPED
    return Order.ShippingStatus.PROCESSING


class Command(BaseCommand):
    help = "Synchronizuje stav zásilky (Zpracovává se/Odesláno/Doručeno) z Packeta packetStatus."

    def handle(self, *args, **options):
        orders = Order.objects.filter(
            status=Order.Status.PAID,
            packeta_tracking_number__isnull=False,
        ).exclude(
            packeta_tracking_number="",
        ).exclude(
            shipping_status=Order.ShippingStatus.DELIVERED,
        )

        count = orders.count()
        self.stdout.write(f"Nalezeno {count} objednávek ke kontrole.")

        updated = 0
        failed = 0
        now = timezone.now()

        for order in orders:
            try:
                result = get_packet_status(order.packeta_tracking_number)
            except PacketaError as e:
                failed += 1
                logger.warning(f"[PacketaStatusSync] Objednávka #{order.id}: {e}")
                continue
            except Exception as e:
                failed += 1
                logger.error(f"[PacketaStatusSync] Objednávka #{order.id} – síťová/jiná chyba: {e}")
                continue

            new_status = _map_status(result.get("code_text"), result.get("name"))
            event_at = _parse_date(result.get("date")) or now

            update_fields = [
                "packeta_last_status_code",
                "packeta_last_status_name",
                "packeta_status_checked_at",
            ]
            order.packeta_last_status_code = result.get("code") or None
            order.packeta_last_status_name = result.get("name") or result.get("code_text") or ""
            order.packeta_status_checked_at = now

            if new_status != order.shipping_status:
                order.shipping_status = new_status
                update_fields.append("shipping_status")

                if new_status == Order.ShippingStatus.SHIPPED and not order.dispatched_at:
                    order.dispatched_at = event_at
                    update_fields.append("dispatched_at")
                elif new_status == Order.ShippingStatus.DELIVERED and not order.delivered_at:
                    order.delivered_at = event_at
                    update_fields.append("delivered_at")
                    if not order.dispatched_at:
                        order.dispatched_at = event_at
                        update_fields.append("dispatched_at")

                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ Objednávka #{order.id}: {order.get_shipping_status_display()} "
                        f"({result.get('name') or result.get('code_text')})"
                    )
                )

            order.save(update_fields=update_fields)

        self.stdout.write(f"\nHotovo: {updated} změn stavu, {failed} chyb, {count} zkontrolováno.")
