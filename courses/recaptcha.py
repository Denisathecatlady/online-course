import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://www.google.com/recaptcha/api/siteverify"


def verify_recaptcha(request, token, action):
    """
    True = pustit dál. False = odmítnout jako podezřelé.

    - Bez nakonfigurovaných klíčů (RECAPTCHA_ENABLED=False): vždy True.
    - Chybějící token: False.
    - Výpadek/timeout Google API: True (fail-open – ať nedostupnost Google
      nezablokuje reálné zákazníky na plateném/kontaktním formuláři).
    - Google "success", ale nesedí action nebo skóre pod prahem: False.
    """
    if not settings.RECAPTCHA_ENABLED:
        return True
    if not token:
        return False

    payload = {
        "secret": settings.RECAPTCHA_SECRET_KEY,
        "response": token,
        "remoteip": request.META.get("REMOTE_ADDR", ""),
    }
    try:
        resp = requests.post(VERIFY_URL, data=payload, timeout=5)
        result = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("reCAPTCHA siteverify nedostupné (%s), propouštím: %s", action, exc)
        return True

    if not result.get("success"):
        logger.info("reCAPTCHA odmítnuto (%s): %s", action, result.get("error-codes"))
        return False
    if result.get("action") != action:
        logger.warning(
            "reCAPTCHA action mismatch (čekáno %s, přišlo %s)", action, result.get("action")
        )
        return False
    if result.get("score", 0) < settings.RECAPTCHA_SCORE_THRESHOLD:
        logger.info("reCAPTCHA nízké skóre %.2f (%s)", result.get("score", 0), action)
        return False
    return True
