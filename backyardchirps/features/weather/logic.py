import logging
from dataclasses import dataclass
from enum import StrEnum

from django.core.cache import cache

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.integrations.open_meteo import fetch_current_weather

logger = logging.getLogger(__name__)

_CACHE_TTL: int = 600

_CLEAR_CODES: frozenset[int] = frozenset({0})
_CLOUDY_CODES: frozenset[int] = frozenset({1, 2, 3})
_FOG_CODES: frozenset[int] = frozenset({45, 48})
_RAIN_CODES: frozenset[int] = frozenset({51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82})
_SNOW_CODES: frozenset[int] = frozenset({71, 73, 75, 77, 85, 86})
_THUNDERSTORM_CODES: frozenset[int] = frozenset({95, 96, 99})

_COMPASS_DIRECTIONS: tuple[str, ...] = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")


class WeatherCondition(StrEnum):
    """
    Open-Meteo's WMO weather codes, grouped down to the few cases the frontend has an
    icon for.
    """

    CLEAR_DAY = "clear_day"
    CLEAR_NIGHT = "clear_night"
    CLOUDY = "cloudy"
    FOG = "fog"
    RAIN = "rain"
    SNOW = "snow"
    THUNDERSTORM = "thunderstorm"
    UNKNOWN = "unknown"


@dataclass
class WeatherReading:
    """
    The weather at the station right now. Always Celsius and km/h in here, whatever the
    user has chosen. The conversion happens on the way out, in
    serialize_weather_reading.
    """

    temperature_celsius: float
    condition: WeatherCondition
    wind_speed_kmh: float
    wind_direction_degrees: float


class WeatherService:
    """
    Reads the weather at the station's location from Open-Meteo, and caches it.
    """

    def get_current(self) -> WeatherReading | None:
        """
        None when no location is configured, or when the call to Open-Meteo fails. A
        successful reading is cached for ten minutes.
        """
        latitude = Settings.get(SettingsKey.LOCATION_LAT)
        longitude = Settings.get(SettingsKey.LOCATION_LON)
        if latitude is None or longitude is None:
            logger.warning("Weather fetch skipped: lat=%s lon=%s", bool(latitude), bool(longitude))
            return None

        cache_key = f"weather_current_{round(latitude, 2)}_{round(longitude, 2)}"
        cached: WeatherReading | None = cache.get(cache_key)
        if cached is not None:
            return cached

        result = self._fetch_and_build(latitude, longitude)
        if result is not None:
            cache.set(cache_key, result, timeout=_CACHE_TTL)
        return result

    def _fetch_and_build(self, latitude: float, longitude: float) -> WeatherReading | None:
        data = fetch_current_weather(latitude, longitude)
        if data is None:
            return None
        temperature = data.get("temperature_2m")
        weather_code = data.get("weather_code")
        wind_speed = data.get("wind_speed_10m")
        wind_direction = data.get("wind_direction_10m")
        if temperature is None or weather_code is None or wind_speed is None or wind_direction is None:
            return None
        return WeatherReading(
            temperature_celsius=float(temperature),
            condition=_condition_from_weather_code(int(weather_code), bool(data.get("is_day", 1))),
            wind_speed_kmh=float(wind_speed),
            wind_direction_degrees=float(wind_direction),
        )


def serialize_weather_reading(
    reading: WeatherReading | None, temperature_unit: str, wind_speed_unit: str
) -> dict[str, object]:
    """
    Turn a reading into JSON, converting the temperature and the wind speed to the units
    asked for. With no reading to show, every field comes back null.
    """
    if reading is None:
        return {
            "temperature": None,
            "temperature_unit": temperature_unit,
            "condition": None,
            "wind_speed": None,
            "wind_speed_unit": wind_speed_unit,
            "wind_direction_degrees": None,
            "wind_direction_compass": None,
        }

    temperature = reading.temperature_celsius
    if temperature_unit == "fahrenheit":
        temperature = temperature * 9 / 5 + 32

    wind_speed = reading.wind_speed_kmh
    if wind_speed_unit == "mph":
        wind_speed = wind_speed * 0.621371

    return {
        "temperature": round(temperature, 1),
        "temperature_unit": temperature_unit,
        "condition": reading.condition.value,
        "wind_speed": round(wind_speed, 1),
        "wind_speed_unit": wind_speed_unit,
        "wind_direction_degrees": reading.wind_direction_degrees,
        "wind_direction_compass": _compass_from_degrees(reading.wind_direction_degrees),
    }


def _condition_from_weather_code(weather_code: int, is_day: bool) -> WeatherCondition:
    """
    Anything the lists above do not cover comes back as UNKNOWN.
    """
    if weather_code in _CLEAR_CODES:
        return WeatherCondition.CLEAR_DAY if is_day else WeatherCondition.CLEAR_NIGHT
    if weather_code in _CLOUDY_CODES:
        return WeatherCondition.CLOUDY
    if weather_code in _FOG_CODES:
        return WeatherCondition.FOG
    if weather_code in _RAIN_CODES:
        return WeatherCondition.RAIN
    if weather_code in _SNOW_CODES:
        return WeatherCondition.SNOW
    if weather_code in _THUNDERSTORM_CODES:
        return WeatherCondition.THUNDERSTORM
    return WeatherCondition.UNKNOWN


def _compass_from_degrees(degrees: float) -> str:
    """
    Turn a wind direction in degrees, where 0 is north, into one of the eight compass
    points.
    """
    index = round((degrees % 360) / 45) % 8
    return _COMPASS_DIRECTIONS[index]
