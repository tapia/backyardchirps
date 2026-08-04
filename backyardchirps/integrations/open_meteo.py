import logging
from typing import cast

import requests

logger = logging.getLogger(__name__)

_API_URL = "https://api.open-meteo.com/v1/forecast"


def fetch_current_weather(latitude: float, longitude: float) -> dict | None:
    """
    The 'current' block of the API response, or None if anything at all went wrong.
    """
    try:
        response = requests.get(
            _API_URL,
            params={
                "latitude": str(latitude),
                "longitude": str(longitude),
                "current": "temperature_2m,weather_code,is_day,wind_speed_10m,wind_direction_10m",
                "timezone": "auto",
            },
            timeout=5,
        )
        response.raise_for_status()
        return cast(dict, response.json()["current"])
    except Exception:
        logger.exception("Open-Meteo fetch failed for lat=%s lon=%s", latitude, longitude)
        return None
