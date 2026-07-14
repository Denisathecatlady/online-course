"""
Packeta / Zásilkovna – integrace přes SOAP XML API.

Dokumentace: https://docs.packeta.com/api-reference/

Endpoint:  https://www.zasilkovna.cz/api/rest
Formát:    SOAP 1.1 / XML
"""

import base64
import logging
import xml.etree.ElementTree as ET

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# SOAP endpoint
# ──────────────────────────────────────────────────────────
PACKETA_SOAP_URL = "https://www.zasilkovna.cz/api/rest"
PACKETA_TIMEOUT = 20  # sekund


# ──────────────────────────────────────────────────────────
# Výjimka
# ──────────────────────────────────────────────────────────

class PacketaError(Exception):
    """Chyba vrácená Packeta API."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Packeta [{code}]: {message}")


# ──────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────

def _escape(value: str) -> str:
    """Escapuje speciální XML znaky v hodnotě."""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _soap_call(method: str, inner_xml: str) -> ET.Element:
    """
    Odešle XML požadavek na Packeta API a vrátí kořenový element odpovědi.

    Přes název je to legacy "REST" XML API (endpoint /api/rest), NE SOAP –
    kořenový element požadavku je přímo název metody, žádná soap:Envelope
    obálka. Vyhodí PacketaError pokud API vrátí chybu, nebo requests
    výjimku při síťové chybě.
    """
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f"<{method}>"
        f"{inner_xml}"
        f"</{method}>"
    )

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
    }

    response = requests.post(
        PACKETA_SOAP_URL,
        data=envelope.encode("utf-8"),
        headers=headers,
        timeout=PACKETA_TIMEOUT,
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)

    # Packeta vrací <status>ok</status>, jinak <status>fault</status>/<status>error</status>
    # s chybovým kódem v <fault> a lidsky čitelnou zprávou v <string>.
    status_el = root.find(".//status")
    if status_el is not None and status_el.text != "ok":
        code = root.findtext(".//fault") or "ERROR"
        msg = (
            root.findtext(".//string")
            or root.findtext(".//message")
            or "Packeta vrátila chybu bez detailů."
        )
        raise PacketaError(code, msg)

    return root


# ──────────────────────────────────────────────────────────
# Hlavní funkce
# ──────────────────────────────────────────────────────────

def create_packet(order) -> dict:
    """
    Vytvoří zásilku v Packeta systému.

    Vrací:
        {
            "packet_id": "Z1234567890",
            "tracking_number": "Z1234567890",
        }

    Vyhodí:
        PacketaError  – Packeta odmítla zásilku (chybná data, apod.)
        ValueError    – Chybí povinné pole (packeta_point_id, heslo)
        requests.*    – Síťová chyba
    """
    if not order.packeta_point_id:
        raise ValueError("Chybí packeta_point_id pro vytvoření zásilky.")

    # ── MOCK režim ─────────────────────────────────────────
    if getattr(settings, "PACKETA_MODE", "live") == "mock":
        suffix = str(order.id).zfill(8)
        mock_id = f"ZMOCK{suffix}"
        logger.info(f"[Packeta MOCK] Zásilka pro objednávku #{order.id}: {mock_id}")
        return {
            "packet_id": mock_id,
            "tracking_number": mock_id,
        }

    # ── LIVE režim ─────────────────────────────────────────
    api_password = getattr(settings, "PACKETA_API_PASSWORD", None)
    if not api_password:
        raise ValueError("Chybí PACKETA_API_PASSWORD pro live Packeta režim.")

    # Jméno a příjmení – Packeta vyžaduje zvlášť
    name = _escape(order.first_name or "")
    surname = _escape(order.last_name or "")
    email = _escape(order.buyer_email or "")
    phone = _escape(getattr(order, "phone", "") or "")
    address_id = _escape(order.packeta_point_id)
    value = float(order.total_price)
    cod = 0  # dobírka – u online platby Stripe vždy 0
    currency = "CZK"
    weight = float(getattr(settings, "PACKETA_DEFAULT_WEIGHT", 0.5))
    eshop = _escape(getattr(settings, "PACKETA_ESHOP_NAME", "CalmDog"))
    number = str(order.id)  # číslo objednávky v e-shopu

    inner_xml = (
        f"<apiPassword>{_escape(api_password)}</apiPassword>"
        f"<packetAttributes>"
        f"  <number>{_escape(number)}</number>"
        f"  <name>{name}</name>"
        f"  <surname>{surname}</surname>"
        f"  <email>{email}</email>"
        f"  <phone>{phone}</phone>"
        f"  <addressId>{address_id}</addressId>"
        f"  <cod>{cod}</cod>"
        f"  <value>{value:.2f}</value>"
        f"  <currency>{currency}</currency>"
        f"  <weight>{weight:.3f}</weight>"
        f"  <eshop>{eshop}</eshop>"
        f"</packetAttributes>"
    )

    root = _soap_call("createPacket", inner_xml)

    # Packeta zabaluje výsledek do <result>/<r> (dle verze API) s <id> zásilky uvnitř;
    # zkusíme i starší tvar <packetId> pro jistotu.
    packet_id_el = root.find(".//packetId")
    if packet_id_el is None:
        packet_id_el = root.find(".//result/id")
    if packet_id_el is None:
        packet_id_el = root.find(".//id")
    if packet_id_el is None or not packet_id_el.text:
        raw = ET.tostring(root, encoding="unicode")
        logger.error(f"[Packeta] Odpověď bez packetId (objednávka #{order.id}): {raw[:2000]}")
        raise PacketaError("NO_ID", f"Packeta nevrátila packetId. Odpověď: {raw[:500]}")

    packet_id = packet_id_el.text.strip()
    barcode_el = root.find(".//barcode")
    tracking = barcode_el.text.strip() if barcode_el is not None and barcode_el.text else packet_id

    logger.info(f"[Packeta] Zásilka vytvořena: {packet_id} (objednávka #{order.id})")
    return {
        "packet_id": packet_id,
        "tracking_number": tracking,
    }


def get_packet_label_pdf(packet_id: str, format: str = "A6 on A4", offset: int = 0) -> bytes:
    """
    Stáhne štítek zásilky jako PDF (base64 dekódovaný).

    Args:
        packet_id:  ID zásilky (např. "Z1234567890")
        format:     "A6 on A4" nebo "A6 on A6"
        offset:     pozice štítku na stránce (0-3)

    Vrací:
        bytes – raw PDF obsah

    Vyhodí:
        PacketaError  – zásilka nenalezena, chyba API
        ValueError    – MOCK režim nebo chybí heslo
    """
    if getattr(settings, "PACKETA_MODE", "live") == "mock":
        raise ValueError("Štítek není dostupný v MOCK režimu.")

    api_password = getattr(settings, "PACKETA_API_PASSWORD", None)
    if not api_password:
        raise ValueError("Chybí PACKETA_API_PASSWORD.")

    inner_xml = (
        f"<apiPassword>{_escape(api_password)}</apiPassword>"
        f"<packetId>{_escape(packet_id)}</packetId>"
        f"<offset>{int(offset)}</offset>"
        f"<format>{_escape(format)}</format>"
    )

    root = _soap_call("packetLabelPdf", inner_xml)

    # Odpověď obsahuje base64 encoded PDF
    label_el = root.find(".//labelContents")
    if label_el is None or not label_el.text:
        raise PacketaError("NO_LABEL", "Packeta nevrátila obsah štítku.")

    pdf_bytes = base64.b64decode(label_el.text.strip())
    logger.info(f"[Packeta] Štítek stažen pro zásilku {packet_id} ({len(pdf_bytes)} B)")
    return pdf_bytes


def get_packet_status(packet_id: str) -> dict:
    """
    Zjistí aktuální stav zásilky.

    Vrací:
        {
            "code_text": "Delivered",
            "code": 4,
            "name": "Doručeno",
            "date": "2024-06-01",
        }

    Vyhodí:
        PacketaError  – zásilka nenalezena
        ValueError    – MOCK režim nebo chybí heslo
    """
    if getattr(settings, "PACKETA_MODE", "live") == "mock":
        return {
            "code_text": "Accepted",
            "code": 1,
            "name": "Přijato",
            "date": "",
        }

    api_password = getattr(settings, "PACKETA_API_PASSWORD", None)
    if not api_password:
        raise ValueError("Chybí PACKETA_API_PASSWORD.")

    inner_xml = (
        f"<apiPassword>{_escape(api_password)}</apiPassword>"
        f"<packetId>{_escape(packet_id)}</packetId>"
    )

    root = _soap_call("packetStatus", inner_xml)

    return {
        "code_text": (root.findtext(".//codeText") or "").strip(),
        "code": int(root.findtext(".//code") or 0),
        "name": (root.findtext(".//name") or "").strip(),
        "date": (root.findtext(".//date") or "").strip(),
    }


# ── Zpětná kompatibilita s původním voláním ve views.py ───
# (odstraňte až bude views.py aktualizováno)
def create_packeta_shipment(order) -> dict:
    return create_packet(order)
