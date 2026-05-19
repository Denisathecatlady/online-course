import logging
from datetime import date, timedelta

import requests

logger = logging.getLogger(__name__)


def fetch_available_ranges(ical_url: str):
    """
    Fetch iCal URL and return list of (start_date, end_date) tuples.
    Events in the calendar = available periods for the hotel.
    """
    try:
        from icalendar import Calendar
    except ImportError:
        logger.error("icalendar library not installed. Run: pip install icalendar")
        return []

    try:
        response = requests.get(ical_url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch iCal URL: {e}")
        return []

    try:
        cal = Calendar.from_ical(response.content)
    except Exception as e:
        logger.error(f"Failed to parse iCal data: {e}")
        return []

    ranges = []
    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        dtstart = component.get("DTSTART")
        dtend = component.get("DTEND")

        if not dtstart or not dtend:
            continue

        start = dtstart.dt
        end = dtend.dt

        # Convert datetime → date if needed
        if hasattr(start, "date"):
            start = start.date()
        if hasattr(end, "date"):
            end = end.date()

        if isinstance(start, date) and isinstance(end, date) and end > start:
            ranges.append((start, end))

    return sorted(ranges, key=lambda r: r[0])


def get_available_date_strings(ical_url: str, booked_dates: set) -> list:
    """
    Returns sorted list of available date strings (YYYY-MM-DD).
    Excludes dates already covered by confirmed/pending reservations.
    """
    ranges = fetch_available_ranges(ical_url)

    available = []
    today = date.today()

    for start, end in ranges:
        current = max(start, today)  # don't show past dates
        while current < end:
            if current not in booked_dates:
                available.append(current.isoformat())
            current += timedelta(days=1)

    return available
