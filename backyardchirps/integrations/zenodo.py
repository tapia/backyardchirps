import logging
import os
from pathlib import Path
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# Of the builds in this Zenodo record we take the full-precision (fp32) one. On a CPU it
# is the faster choice, because onnxruntime converts the fp16 builds back to fp32 anyway,
# and it is the build the published accuracy figures refer to. The label CSV must come
# from the same build, since its rows line up with the model's output classes.
_RECORD = "https://zenodo.org/records/20703646/files"
_MODEL_NAME = "BirdNET+_V3.0-preview3.1_Global_11K_FP32.onnx"
_LABELS_NAME = "BirdNET+_V3.0-preview3.1_Global_11K_Labels.csv"

BIRDNET3_MODEL_URL = f"{_RECORD}/{quote(_MODEL_NAME)}?download=1"
BIRDNET3_LABELS_URL = f"{_RECORD}/{quote(_LABELS_NAME)}?download=1"
# The published byte size. A local model of this size is taken to be the current one and
# is not downloaded again.
BIRDNET3_MODEL_SIZE = 541598502

_DOWNLOAD_TIMEOUT_SECONDS = 600
_CHUNK_SIZE = 1024 * 1024


def download_file(url: str, destination: Path) -> None:
    """
    Stream a Zenodo file to destination.

    It downloads to a temporary file alongside the destination and then moves it into
    place in one step. A recorder with the model open never reads a half-written file,
    and a download that fails partway leaves the previous copy where it was.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial_destination = destination.with_name(destination.name + ".part")

    logger.info("Downloading %s from Zenodo", destination.name)
    try:
        with requests.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            with open(partial_destination, "wb") as output_file:
                for chunk in response.iter_content(_CHUNK_SIZE):
                    output_file.write(chunk)
        os.replace(partial_destination, destination)
    finally:
        partial_destination.unlink(missing_ok=True)


def fetch_labels_csv() -> str:
    """
    The label CSV as text. Small enough to read into memory instead of streaming.
    """
    response = requests.get(BIRDNET3_LABELS_URL, timeout=_DOWNLOAD_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text
