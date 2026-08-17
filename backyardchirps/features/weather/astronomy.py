import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timezone
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import sunrise
from astral.sun import sunset
from django.conf import settings

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey

logger = logging.getLogger(__name__)

_EVENT_FIELDS: tuple[str, ...] = ("sunrise", "sunset")

# One of astral's sun events, called as event(observer, date, tzinfo=...).
_SunEvent = Callable[..., datetime]


@dataclass
class AstroTimes:
    """
    The astronomical events of one day at the station. Times are timezone-aware and in
    UTC, and a field is None when the sun does not cross the horizon that day.
    """

    sunrise: datetime | None
    sunset: datetime | None


def get_for_date(target_date: date) -> AstroTimes | None:
    """
    Sunrise and sunset at the station on one day, or None when it has no coordinates.

    Both times follow from the coordinates and the date, so this is arithmetic rather
    than a call to a service: no API key, no network, and nothing to cache.
    """
    latitude = Settings.get(SettingsKey.LOCATION_LAT)
    longitude = Settings.get(SettingsKey.LOCATION_LON)
    if latitude is None or longitude is None:
        logger.warning("Astronomy skipped: lat=%s lon=%s", bool(latitude), bool(longitude))
        return None

    observer = Observer(latitude=latitude, longitude=longitude)
    local_tz = ZoneInfo(settings.TIME_ZONE)
    return AstroTimes(
        sunrise=_event_time(sunrise, observer, target_date, local_tz),
        sunset=_event_time(sunset, observer, target_date, local_tz),
    )


def serialize_astro_times(astro_list: list[AstroTimes | None]) -> dict[str, object]:
    """
    Flatten several days into one list of events. Keeping them in a single list lets the
    frontend pick out whichever time window it happens to be showing.
    """
    events: list[dict[str, str]] = []

    for astro_times in astro_list:
        if astro_times is None:
            continue
        for field in _EVENT_FIELDS:
            value: datetime | None = getattr(astro_times, field)
            if value is not None:
                events.append({"key": field, "time": value.isoformat()})

    return {"events": events}


def _event_time(event: _SunEvent, observer: Observer, target_date: date, local_tz: ZoneInfo) -> datetime | None:
    """
    One event as UTC, or None when it does not happen there on that date.

    The date is read in the station's own timezone, so "today" means the day whoever is
    looking at the chart is having. Far enough north or south the sun can stay up or
    stay down for the whole day, and astral raises rather than inventing a time.
    """
    try:
        moment = event(observer, target_date, tzinfo=local_tz)
    except ValueError:
        return None
    return moment.astimezone(timezone.utc).replace(microsecond=0)
