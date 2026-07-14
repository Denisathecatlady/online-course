"""
Google Calendar integrace pro tréninkové rezervace (OAuth).

Každý trenér jednorázově připojí svůj Google účet (viz views: google_oauth_start
/ google_oauth_callback). Uložíme jeho credentials (refresh token) do
`Trainer.google_oauth_token` a jeho jménem pak vytváříme/rušíme události.

Integrace se elegantně přeskočí, pokud:
  - není nastaven GOOGLE_OAUTH_CLIENT_ID/SECRET (GOOGLE_CALENDAR_ENABLED = False),
  - trenér nemá připojený kalendář (trainer.google_ready == False),
  - nejsou nainstalované google knihovny.
Zbytek systému (rezervace, e-maily, profil) funguje i bez Googlu.

Google knihovny se importují líně uvnitř funkcí, aby appka fungovala
i bez nainstalovaných balíčků.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

EVENT_TIMEZONE = "Europe/Prague"


class GoogleCalendarError(Exception):
    """Chyba při komunikaci s Google Calendar API."""


def is_enabled() -> bool:
    return bool(getattr(settings, "GOOGLE_CALENDAR_ENABLED", False))


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI],
        }
    }


# ──────────────────────────────────────────────────────────
# OAuth flow (připojení kalendáře trenéra)
# ──────────────────────────────────────────────────────────

def build_flow(state=None):
    """Vytvoří OAuth Flow pro přihlášení trenéra přes Google."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(),
        scopes=settings.GOOGLE_CALENDAR_SCOPES,
        state=state,
    )
    flow.redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI
    return flow


def save_credentials(trainer, credentials) -> None:
    """Uloží credentials (vč. refresh tokenu) k trenérovi."""
    trainer.google_oauth_token = credentials.to_json()
    trainer.google_connected = True
    trainer.save(update_fields=["google_oauth_token", "google_connected"])


def _load_credentials(trainer):
    """Načte credentials, případně obnoví vypršelý access token a uloží ho zpět."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    if not trainer.google_oauth_token:
        return None

    creds = Credentials.from_authorized_user_info(
        json.loads(trainer.google_oauth_token),
        settings.GOOGLE_CALENDAR_SCOPES,
    )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        trainer.google_oauth_token = creds.to_json()
        trainer.save(update_fields=["google_oauth_token"])

    return creds


def _get_service(trainer):
    from googleapiclient.discovery import build

    creds = _load_credentials(trainer)
    if creds is None:
        return None
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


# ──────────────────────────────────────────────────────────
# Události
# ──────────────────────────────────────────────────────────

def list_events(trainer, calendar_id, time_min, time_max):
    """
    Načte události z daného kalendáře trenéra v rozsahu [time_min, time_max].

    Vrací list normalizovaných dictů:
        {
          "event_id": str,          # unikátní i pro jednotlivé instance opakování
          "summary": str,
          "start_dt": datetime|None,  # None u celodenních událostí
          "end_dt": datetime|None,
          "status": str,            # "confirmed" / "cancelled" / ...
          "all_day": bool,
        }

    `singleEvents=True` rozbalí opakující se události na jednotlivé instance,
    takže trenér může nastavit např. týdenní dostupnost a každý týden vznikne
    samostatné okno. Vrací [] když je integrace vypnutá / trenér nepřipojen /
    nastane chyba (volající to ošetří).
    """
    if not is_enabled():
        logger.info("[GCal] Integrace vypnutá – přeskakuji čtení událostí.")
        return []

    if not trainer.google_ready:
        logger.info(f"[GCal] Trenér {trainer} nemá připojený kalendář – přeskakuji čtení.")
        return []

    if not calendar_id:
        return []

    from datetime import datetime

    service = _get_service(trainer)
    if service is None:
        return []

    events = []
    page_token = None
    try:
        while True:
            response = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=250,
                    pageToken=page_token,
                )
                .execute()
            )
            for item in response.get("items", []):
                start = item.get("start", {})
                end = item.get("end", {})
                all_day = "date" in start  # celodenní událost má "date", ne "dateTime"

                start_dt = end_dt = None
                if not all_day:
                    start_raw = start.get("dateTime")
                    end_raw = end.get("dateTime")
                    if start_raw:
                        start_dt = datetime.fromisoformat(start_raw)
                    if end_raw:
                        end_dt = datetime.fromisoformat(end_raw)

                events.append(
                    {
                        "event_id": item.get("id", ""),
                        "summary": item.get("summary", "") or "",
                        "start_dt": start_dt,
                        "end_dt": end_dt,
                        "status": item.get("status", ""),
                        "all_day": all_day,
                    }
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                break
    except Exception as e:
        logger.error(
            f"[GCal] Chyba při čtení událostí z kalendáře {calendar_id} "
            f"(trenér {trainer}): {e}"
        )
        return []

    return events


def _build_event_body(reservation) -> dict:
    slot = reservation.slot
    prefix = "Skupinový trénink" if slot.is_group else "Individuální trénink"
    summary = f"{prefix} – {reservation.full_name}"

    lines = [
        f"Klient: {reservation.full_name}",
        f"E-mail: {reservation.email}",
        f"Telefon: {reservation.phone or '–'}",
        f"Pes: {reservation.dog_name}",
        f"Lokalita: {slot.location.name}",
    ]
    if reservation.note:
        lines.append(f"Poznámka: {reservation.note}")

    return {
        "summary": summary,
        "description": "\n".join(lines),
        "start": {"dateTime": slot.start.isoformat(), "timeZone": EVENT_TIMEZONE},
        "end": {"dateTime": slot.end.isoformat(), "timeZone": EVENT_TIMEZONE},
    }


def create_event(reservation) -> str:
    """Vytvoří událost v kalendáři trenéra. Vrátí event_id, nebo "" když přeskočeno."""
    if not is_enabled():
        logger.info("[GCal] Integrace vypnutá – přeskakuji vytvoření události.")
        return ""

    trainer = reservation.slot.trainer
    if not trainer.google_ready:
        logger.info(f"[GCal] Trenér {trainer} nemá připojený kalendář – přeskakuji.")
        return ""

    try:
        service = _get_service(trainer)
        if service is None:
            return ""
        event = (
            service.events()
            .insert(
                calendarId=trainer.google_calendar_id or "primary",
                body=_build_event_body(reservation),
            )
            .execute()
        )
        event_id = event.get("id", "")
        logger.info(f"[GCal] Událost vytvořena {event_id} (rezervace #{reservation.pk})")
        return event_id
    except Exception as e:
        logger.error(
            f"[GCal] Chyba při vytváření události (rezervace #{reservation.pk}): {e}"
        )
        return ""


def delete_event(reservation) -> bool:
    """Smaže událost z kalendáře trenéra. Vrátí True při úspěchu."""
    if not is_enabled() or not reservation.google_event_id:
        return False

    trainer = reservation.slot.trainer
    if not trainer.google_ready:
        return False

    try:
        service = _get_service(trainer)
        if service is None:
            return False
        service.events().delete(
            calendarId=trainer.google_calendar_id or "primary",
            eventId=reservation.google_event_id,
        ).execute()
        logger.info(f"[GCal] Událost smazána {reservation.google_event_id}")
        return True
    except Exception as e:
        # 404/410 = událost už neexistuje → považujeme za smazané
        logger.warning(
            f"[GCal] Mazání události selhalo (rezervace #{reservation.pk}): {e}"
        )
        return False


def event_exists(reservation):
    """
    Vrátí:
      True  – událost v Google kalendáři stále existuje,
      False – událost byla v Googlu smazaná/zrušená,
      None  – nelze zjistit (integrace vypnutá / chyba) → volající ignoruje.
    """
    if not is_enabled() or not reservation.google_event_id:
        return None

    trainer = reservation.slot.trainer
    if not trainer.google_ready:
        return None

    try:
        from googleapiclient.errors import HttpError

        service = _get_service(trainer)
        if service is None:
            return None
        try:
            event = (
                service.events()
                .get(
                    calendarId=trainer.google_calendar_id or "primary",
                    eventId=reservation.google_event_id,
                )
                .execute()
            )
        except HttpError as he:
            if getattr(he, "resp", None) is not None and he.resp.status in (404, 410):
                return False
            raise
        # Smazané události v Googlu mají status "cancelled"
        if event.get("status") == "cancelled":
            return False
        return True
    except Exception as e:
        logger.warning(f"[GCal] event_exists selhalo (rezervace #{reservation.pk}): {e}")
        return None
