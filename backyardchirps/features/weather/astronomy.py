import logging
from dataclasses import dataclass
from datetime import date
from datetime import datetime
from datetime import timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.cache import cache

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.integrations.ipgeolocation import fetch_astronomy

logger = logging.getLogger(__name__)

_CACHE_TTL: int = 3600
_EVENT_FIELDS: tuple[str, ...] = ("sunrise", "sunset")


@dataclass
class AstroTimes:
    """
    The astronomical events of one day at the station. Times are timezone-aware and in
    UTC, and a field is None when the API did not give it.
    """

    sunrise: datetime | None
    sunset: datetime | None


class AstronomyService:
    """
    Reads sunrise and sunset times from the ipgeolocation.io Astronomy API, and caches
    them.
    """

    def get_for_date(self, target_date: date) -> AstroTimes | None:
        """
        None when no location or no API key is configured. A successful reading is cached
        for one hour.
        """
        api_key = settings.IPGEOLOCATION_API_KEY
        latitude = Settings.get(SettingsKey.LOCATION_LAT)
        longitude = Settings.get(SettingsKey.LOCATION_LON)
        if not api_key or latitude is None or longitude is None:
            logger.warning(
                "Astronomy fetch skipped: api_key=%s lat=%s lon=%s", bool(api_key), bool(latitude), bool(longitude)
            )
            return None

        date_str = target_date.isoformat()
        cache_key = f"astro_times_{latitude}_{longitude}_{date_str}"
        cached: AstroTimes | None = cache.get(cache_key)
        if cached is not None:
            return cached

        result = self._fetch_and_build(api_key, latitude, longitude, date_str)
        if result.sunrise is not None:
            cache.set(cache_key, result, timeout=_CACHE_TTL)
        return result

    def _fetch_and_build(self, api_key: str, latitude: float, longitude: float, date_str: str) -> AstroTimes:
        data = fetch_astronomy(api_key, latitude, longitude, date_str)
        if data is None:
            return self._empty()

        local_tz = ZoneInfo(settings.TIME_ZONE)
        api_date_str = data.get("date", "")
        if not isinstance(api_date_str, str) or not api_date_str:
            api_date_str = date_str

        return AstroTimes(
            sunrise=self._parse_time(api_date_str, data.get("sunrise"), local_tz),
            sunset=self._parse_time(api_date_str, data.get("sunset"), local_tz),
        )

    def _empty(self) -> AstroTimes:
        return AstroTimes(sunrise=None, sunset=None)

    def _parse_time(self, date_str: str, time_value: object, local_tz: ZoneInfo) -> datetime | None:
        if not isinstance(time_value, str) or not time_value or time_value.startswith("-"):
            return None
        try:
            local_dt = datetime.strptime(f"{date_str} {time_value}", "%Y-%m-%d %H:%M").replace(tzinfo=local_tz)
            return local_dt.astimezone(timezone.utc)
        except ValueError:
            return None


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
