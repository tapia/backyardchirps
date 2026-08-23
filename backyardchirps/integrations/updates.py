import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_MANIFEST_URL = "https://github.com/tapia/backyardchirps/releases/latest/download/manifest.json"
MANIFEST_URL = os.environ.get("BACKYARDCHIRPS_MANIFEST_URL") or DEFAULT_MANIFEST_URL

_TIMEOUT_SECONDS = 15


def fetch_manifest() -> dict[str, Any]:
    """
    The published manifest of the latest release.
    """
    response = requests.get(MANIFEST_URL, timeout=_TIMEOUT_SECONDS)
    response.raise_for_status()
    manifest = response.json()
    if not isinstance(manifest, dict):
        raise ValueError("The release manifest is not a JSON object.")
    return manifest
