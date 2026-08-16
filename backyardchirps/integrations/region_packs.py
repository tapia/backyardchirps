import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Packs are built and published from their own repository, so this is the only place a
# station learns they exist. The index is read from the branch rather than from a release,
# because it changes whenever any pack is rebuilt and a release per index entry would say
# nothing extra.
#
# Overridable through the environment, which is what makes the pack step something a
# developer can actually look at: point it at a file served on localhost and the wizard
# offers whatever that file lists. It also leaves room for anyone who would rather build
# and host their own packs than use these.
DEFAULT_INDEX_URL = "https://raw.githubusercontent.com/tapia/backyardchirps-regional-packs/main/index.json"
INDEX_URL = os.environ.get("BACKYARDCHIRPS_PACKS_INDEX_URL") or DEFAULT_INDEX_URL

# Short on purpose. The index is a small JSON file, and this request is made while
# somebody is looking at the settings page or the wizard, on a web process with four
# request slots. A station with no route to the internet should be told so quickly rather
# than holding a slot open.
_INDEX_TIMEOUT_SECONDS = 10
# A pack is hundreds of megabytes and a Pi is often on wifi at the end of a garden.
_DOWNLOAD_TIMEOUT_SECONDS = 3600
_CHUNK_SIZE = 1024 * 1024


def fetch_index() -> list[dict[str, Any]]:
    """
    Every published pack, as the index lists it. Each entry carries the box it covers and
    what a download needs: the URL, the size and the sha256.

    Plain dictionaries, not entities. Reading meaning out of them is the caller's job.
    """
    response = requests.get(INDEX_URL, timeout=_INDEX_TIMEOUT_SECONDS)
    response.raise_for_status()
    packs = response.json().get("packs", [])
    if not isinstance(packs, list):
        raise ValueError("The packs index does not hold a list of packs.")
    return packs


def download_pack(url: str, destination: Path, on_progress: Callable[[int, int], None] | None = None) -> None:
    """
    Stream a pack to destination, reporting bytes received and bytes expected as it goes.

    It writes beside the destination and moves the file into place in one step, so a
    download that fails partway leaves nothing that looks finished. on_progress is called
    often enough to drive a progress bar; expected is 0 when the server does not say.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial_destination = destination.with_name(destination.name + ".part")

    logger.info("Downloading region pack %s", destination.name)
    try:
        with requests.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            expected = int(response.headers.get("Content-Length") or 0)
            received = 0
            with open(partial_destination, "wb") as output_file:
                for chunk in response.iter_content(_CHUNK_SIZE):
                    output_file.write(chunk)
                    received += len(chunk)
                    if on_progress is not None:
                        on_progress(received, expected)
        os.replace(partial_destination, destination)
    finally:
        partial_destination.unlink(missing_ok=True)
