import json
import logging
import urllib.request
from typing import cast

logger = logging.getLogger(__name__)

_TAXONOMY_URL = "https://birdnet.cornell.edu/taxonomy/api/download/json"


def download_taxonomy() -> list[dict]:
    """
    Download the taxonomy from the BirdNET API.
    """
    logger.info("Downloading taxonomy from %s", _TAXONOMY_URL)
    with urllib.request.urlopen(_TAXONOMY_URL, timeout=60) as response:
        return cast(list[dict], json.loads(response.read()))
