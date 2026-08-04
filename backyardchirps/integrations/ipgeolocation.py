import logging
from typing import cast

import requests

logger = logging.getLogger(__name__)

_API_URL = "https://api.ipgeolocation.io/v2/astronomy"


def fetch_astronomy(api_key: str, lat: float, lon: float, date_str: str) -> dict | None:
    """
    The 'astronomy' block of the API response, or None if anything at all went wrong.
    """
    try:
        response = requests.get(
            _API_URL,
            params={"apiKey": api_key, "lat": str(lat), "long": str(lon), "date": date_str},
            timeout=5,
        )
        response.raise_for_status()
        return cast(dict, response.json()["astronomy"])
    except Exception:
        logger.exception("ipgeolocation.io fetch failed for date=%s lat=%s lon=%s", date_str, lat, lon)
        return None
