import json
import logging
from pathlib import Path

from django.conf import settings

from backyardchirps.features.species.entity import Species

logger = logging.getLogger(__name__)

# What the builder writes, and all a species page can draw. A pack from a newer builder
# may hold more per recording, and this drops it rather than passing it through.
_MAX_RECORDINGS = 5


def get_reference_calls(species: Species) -> list[dict]:
    """
    Example recordings of this species, as the installed region pack carries them.

    Empty for a station with no pack, for a pack built before reference calls existed,
    and for a species that does not live in that region. All three are working states:
    the species page then shows no reference calls and nothing else changes.

    The recordings themselves stay on xeno-canto. A pack carries the addresses, which is
    the part that used to need an API key, never the audio.
    """
    path = Path(settings.SPECIES_REFERENCE_CALLS_DIR) / f"{species.slug}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        logger.warning("Reference calls for %s could not be read from %s", species.slug, path, exc_info=True)
        return []
    return _understood(raw)


def _understood(raw: object) -> list[dict]:
    """
    Keep the recordings this can draw and drop the rest.

    A pack is a large file from the internet, so what comes out of one is read the way
    the packs index already is: field by field, refusing anything malformed rather than
    handing it to the frontend. A recording with no address is dropped, since that is the
    one field with no sensible empty value.
    """
    if not isinstance(raw, list):
        logger.warning("A reference calls file does not hold a list, so it was ignored")
        return []

    recordings = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        url = entry.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        recordings.append(
            {
                "url": url,
                "type": _text(entry.get("type")),
                "sex": _text(entry.get("sex")),
                "stage": _text(entry.get("stage")),
                "length": _text(entry.get("length")),
            }
        )
        if len(recordings) == _MAX_RECORDINGS:
            break
    return recordings


def _text(value: object) -> str | None:
    """
    A field the frontend shows as text, or None where it shows a dash.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None
