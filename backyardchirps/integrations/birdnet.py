import json
import logging
import urllib.request
from typing import cast

logger = logging.getLogger(__name__)

_TAXONOMY_URL = "https://birdnet.cornell.edu/taxonomy/api/download/json"

# The taxonomy holds over ten thousand species and only ever grows, so anything under this
# is a truncated response or a different endpoint, never a real answer. Nothing downstream
# would notice on its own: a station would simply stop knowing most birds, and a package
# built from it would ship that.
_MINIMUM_SPECIES = 10_000

# Every entry carries these, empty where upstream has nothing. Their absence means the
# shape changed, which is worth stopping for.
_REQUIRED_KEYS = ("scientific_name", "common_names", "ebird_code")


class TaxonomyDownloadError(RuntimeError):
    """
    Raised when the taxonomy that came back is not one, so no caller ever writes it over
    the copy it already has.
    """


def download_taxonomy() -> list[dict]:
    logger.info("Downloading taxonomy from %s", _TAXONOMY_URL)
    with urllib.request.urlopen(_TAXONOMY_URL, timeout=60) as response:
        taxa = json.loads(response.read())

    check_taxonomy(taxa)
    logger.info("Downloaded %d species", len(taxa))
    return cast(list[dict], taxa)


def check_taxonomy(taxa: object) -> None:
    """
    Refuse a payload that is not a full taxonomy.
    """
    if not isinstance(taxa, list):
        raise TaxonomyDownloadError(f"Expected a list of species, got {type(taxa).__name__}")

    if len(taxa) < _MINIMUM_SPECIES:
        raise TaxonomyDownloadError(f"Only {len(taxa)} species, expected at least {_MINIMUM_SPECIES}")

    for position, taxon in enumerate(taxa):
        if not isinstance(taxon, dict):
            raise TaxonomyDownloadError(f"Entry {position} is a {type(taxon).__name__}, not an object")
        missing = [key for key in _REQUIRED_KEYS if key not in taxon]
        if missing:
            raise TaxonomyDownloadError(f"Entry {position} has no {', '.join(missing)}")
        if not taxon["scientific_name"]:
            raise TaxonomyDownloadError(f"Entry {position} has an empty scientific_name")
