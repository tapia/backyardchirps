import logging

import requests

logger = logging.getLogger(__name__)

_API_URL = "https://xeno-canto.org/api/3/recordings"


def get_recordings(api_key: str, scientific_name: str, limit: int = 5) -> list[dict]:
    """
    Up to `limit` recordings of the species, or an empty list if anything at all went
    wrong.
    """
    try:
        query = f'sp:"{scientific_name}"+q:">C"'
        response = requests.get(
            f"{_API_URL}?query={query}&key={api_key}",
            timeout=5,
        )
        response.raise_for_status()

        sounds = []
        for recording in response.json().get("recordings", []):
            file_url = recording.get("file", "")
            if file_url.startswith("//"):
                file_url = "https:" + file_url
            if not file_url:
                continue
            sounds.append(
                {
                    "url": file_url,
                    "type": _clean_field(recording.get("type")),
                    "sex": _clean_field(recording.get("sex")),
                    "stage": _clean_field(recording.get("stage")),
                    "length": recording.get("length") or None,
                }
            )
            if len(sounds) == limit:
                break
        return sounds
    except Exception:
        logger.exception("Xeno-Canto fetch failed for %s", scientific_name)
        return []


def _clean_field(value: object) -> str | None:
    if not value or (isinstance(value, str) and value.strip().lower() == "uncertain"):
        return None
    return str(value)
