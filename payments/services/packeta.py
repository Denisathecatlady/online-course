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
    Odešle SOAP požadavek na Packeta API a vrátí kořenový element odpovědi.
    Vyhodí PacketaError pokud API vrátí chybu, nebo requests výjimku při síťové chybě.
    """
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        "<soap:Body>"
        f"<{method}>"
        f"{inner_xml}"
        f"</{method}>"
        "</soap:Body>"
        "</soap:Envelope>"
    )

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": method,
    }

    response = requests.post(
        PACKETA_SOAP_URL,
        data=envelope.encode("utf-8"),
        headers=headers,
        timeout=PACKETA_TIMEOUT,
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    ns = {"soap": "http://schemas.xmlsoap.org/soap/envelope/"}

    # Hledáme chybový element (fault nebo status=error)
    fault = root.find(".//soap:Fault", ns)
    if fault is not None:
        code = fault.findtext("faultcode") or "FAULT"
        msg = fault.findtext("faultstring") or "Unknown SOAP fault"
        raise PacketaError(code, msg)

    # Packeta vrací <status>ok</status> nebo <status>error</status>
    status_el = root.find(".//status")
    if status_el is not None and status_el.text == "error":
        fault_el = root.find(".//fault")
        if fault_el is not None:
            code = fault_el.findtext("code") or "ERROR"
            msg = fault_el.findtext("message") or "Unknown Packeta error"
        else:
            code = "ERROR"
            msg = "Packeta vrátila chybu bez detailů."
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

    packet_id_el = root.find(".//result/id")
    if packet_id_el is None or not packet_id_el.text:
        raise PacketaError("NO_ID", "Packeta nevrátila packetId.")

    packet_id = packet_id_el.text.strip()
    barcode_el = root.find(".//result/barcode")
    tracking = barcode_el.text.strip() if barcode_el is not None and barcode_el.text else packet_id

    logger.info(f"[Packeta] Zásilka vytvořena: {packet_id} (objednávka #{order.id})")
    return {
        "packet_id": packet_id,
        "tracking_number": tracking,
    }


def create_packet_claim(order) -> dict:
    """
    Vytvoří vratkovou zásilku (reklamace/vrácení zboží) k původní zásilce a vrátí
    vratkový kód. Packeta na žádost pošle štítek/kód i e-mailem zákazníkovi
    (sendLabelToEmail).

    Vrací:
        {
            "packet_id": "Z9876543210",
            "barcode": "Z9876543210",
            "barcode_text": "9876543210",  # vratkový kód k zobrazení zákazníkovi
        }

    Vyhodí:
        PacketaError  – Packeta odmítla vratku (např. neplatné číslo původní zásilky)
        ValueError    – chybí sledovací číslo původní zásilky nebo heslo
        requests.*    – síťová chyba
    """
    if not order.packeta_tracking_number:
        raise ValueError("Chybí packeta_tracking_number – objednávka nemá zásilku Packeta.")

    # ── MOCK režim ─────────────────────────────────────────
    if getattr(settings, "PACKETA_MODE", "live") == "mock":
        suffix = str(order.id).zfill(8)
        mock_id = f"ZRETMOCK{suffix}"
        logger.info(f"[Packeta MOCK] Vratka pro objednávku #{order.id}: {mock_id}")
        return {
            "packet_id": mock_id,
            "barcode": mock_id,
            "barcode_text": suffix,
        }

    # ── LIVE režim ─────────────────────────────────────────
    api_password = getattr(settings, "PACKETA_API_PASSWORD", None)
    if not api_password:
        raise ValueError("Chybí PACKETA_API_PASSWORD pro live Packeta režim.")

    number = _escape(order.packeta_tracking_number)
    email = _escape(order.buyer_email or "")
    phone = _escape(getattr(order, "phone", "") or "")
    value = float(order.total_price)
    currency = "CZK"
    eshop = _escape(getattr(settings, "PACKETA_ESHOP_NAME", "CalmDog"))

    inner_xml = (
        f"<apiPassword>{_escape(api_password)}</apiPassword>"
        f"<claimAttributes>"
        f"  <number>{number}</number>"
        f"  <email>{email}</email>"
        f"  <phone>{phone}</phone>"
        f"  <value>{value:.2f}</value>"
        f"  <currency>{currency}</currency>"
        f"  <eshop>{eshop}</eshop>"
        f"  <sendLabelToEmail>1</sendLabelToEmail>"
        f"</claimAttributes>"
    )

    root = _soap_call("createPacketClaim", inner_xml)

    packet_id_el = root.find(".//result/id")
    if packet_id_el is None or not packet_id_el.text:
        raise PacketaError("NO_ID", "Packeta nevrátila ID vratkové zásilky.")

    packet_id = packet_id_el.text.strip()
    barcode_el = root.find(".//result/barcode")
    barcode = barcode_el.text.strip() if barcode_el is not None and barcode_el.text else packet_id
    barcode_text_el = root.find(".//result/barcodeText")
    barcode_text = barcode_text_el.text.strip() if barcode_text_el is not None and barcode_text_el.text else barcode

    logger.info(f"[Packeta] Vratka vytvořena: {packet_id} (objednávka #{order.id})")
    return {
        "packet_id": packet_id,
        "barcode": barcode,
        "barcode_text": barcode_text,
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

    # Odpověď obsahuje base64 encoded PDF přímo jako text elementu <result>
    label_el = root.find(".//result")
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
            "code_text": "delivered",
            "code": 4,
            "name": "Zásilka byla doručena.",
            "date": "2024-06-01T10:15:00",
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

    # Aktuální stav je v <r><record>...</record></r> – code/name/date žijí
    # pod record jako statusCode/statusText/dateTime, ne přímo pod response.
    record = root.find(".//record")
    if record is None:
        return {"code_text": "", "code": 0, "name": "", "date": ""}

    return {
        "code_text": (record.findtext("codeText") or "").strip(),
        "code": int(record.findtext("statusCode") or 0),
        "name": (record.findtext("statusText") or "").strip(),
        "date": (record.findtext("dateTime") or "").strip(),
    }


# ── Zpětná kompatibilita s původním voláním ve views.py ───
# (odstraňte až bude views.py aktualizováno)
def create_packeta_shipment(order) -> dict:
    return create_packet(order)
