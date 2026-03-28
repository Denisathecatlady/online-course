import requests
from django.conf import settings


def create_packeta_shipment(order):
    """
    Vytvoří zásilku v Packeta systému.
    Vrací dict:
    {
        "packet_id": ...,
        "tracking_number": ...
    }
    """

    if not order.packeta_point_id:
        raise ValueError("Chybí packeta_point_id pro vytvoření zásilky.")

    if settings.PACKETA_MODE == "mock":
        packet_suffix = str(order.id).zfill(6)
        return {
            "packet_id": f"mock-packet-{packet_suffix}",
            "tracking_number": f"MOCKTRACK{packet_suffix}",
        }

    if not settings.PACKETA_API_PASSWORD:
        raise ValueError("Chybí PACKETA_API_PASSWORD pro live Packeta režim.")

    payload = {
        "apiPassword": settings.PACKETA_API_PASSWORD,
        "packet": {
            "name": f"{order.first_name} {order.last_name}",
            "email": order.buyer_email,
            "addressId": order.packeta_point_id,
            "value": float(order.total_price),
            "eshop": "CalmDog",
        }
    }

    response = requests.post(settings.PACKETA_API_URL, json=payload, timeout=15)
    response.raise_for_status()

    data = response.json()

    if "packetId" not in data:
        raise Exception(f"Packeta error: {data}")

    return {
        "packet_id": data["packetId"],
        "tracking_number": data.get("barcode"),
    }
