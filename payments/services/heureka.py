"""
Heureka „Ověřeno zákazníky" – odeslání objednávky pro rozeslání dotazníku
spokojenosti zákazníkům.

⚠️ NEOVĚŘENÝ API KONTRAKT ⚠️
V době vzniku tohoto modulu obchod ještě NEMÁ aktivní Heureka „Ověřeno
zákazníky" účet ani API klíč. Endpoint (HEUREKA_API_URL) a názvy polí
v payloadu níže vycházejí z běžně publikovaného Heureka Order API, ale
NEBYLY ověřeny proti reálnému účtu ani sandboxu.

PŘED NASAZENÍM DO PRODUKCE:
  1. Ověř přesný endpoint, autentizaci a povinná pole podle dokumentace,
     kterou Heureka zašle po schválení účtu „Ověřeno zákazníky".
  2. Uprav HEUREKA_API_URL a klíče v payloadu podle skutečné dokumentace.
  3. Otestuj proti Heureka sandboxu, pokud je k dispozici.

Dokud HEUREKA_API_KEY není nastaven (settings.HEUREKA_ENABLED == False),
tento modul pouze loguje a nic neodesílá.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# TODO: OVĚŘIT proti reálné Heureka dokumentaci před produkčním nasazením.
HEUREKA_API_URL = "https://ovnl.heureka.cz/api/v1/order"
HEUREKA_TIMEOUT = 10  # sekund


class HeurekaError(Exception):
    """Chyba vrácená Heureka API."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"Heureka: {message}")


def send_order_review_request(order) -> bool:
    """
    Odešle e-mail zákazníka a číslo objednávky do Heureka Ověřeno zákazníky,
    aby Heureka mohla zaslat dotazník spokojenosti.

    No-op (vrací False, jen loguje), pokud:
      - HEUREKA_API_KEY není nastaven (settings.HEUREKA_ENABLED == False)
      - order.buyer_email je prázdný

    Vrací:
        True  – požadavek byl úspěšně odeslán Heurece
        False – přeskočeno (integrace vypnutá nebo chybí e-mail)

    Vyhodí:
        HeurekaError  – Heureka API vrátilo chybovou odpověď
        requests.*    – síťová chyba (timeout, DNS, ...)
    """
    if not getattr(settings, "HEUREKA_ENABLED", False):
        logger.info(
            f"[Heureka] Přeskočeno (HEUREKA_API_KEY nenastaven) – objednávka #{order.id}"
        )
        return False

    if not order.buyer_email:
        logger.warning(
            f"[Heureka] Objednávka #{order.id} nemá e-mail zákazníka, přeskočeno."
        )
        return False

    # ── POZOR: NEOVĚŘENÝ payload – viz caveat v hlavičce modulu ──────────
    payload = {
        "key": settings.HEUREKA_API_KEY,   # TODO: ověřit název pole
        "email": order.buyer_email,        # TODO: ověřit název pole
        "orderId": str(order.id),          # TODO: ověřit název pole
        "service": "verified-by-customers",
    }

    response = requests.post(HEUREKA_API_URL, data=payload, timeout=HEUREKA_TIMEOUT)
    response.raise_for_status()

    logger.info(f"[Heureka] Objednávka #{order.id} odeslána do Ověřeno zákazníky.")
    return True
