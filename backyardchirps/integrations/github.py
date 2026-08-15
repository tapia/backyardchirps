import logging
import os
from pathlib import Path
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# GeoModel 3, published by the BirdNET team as release assets. Of the two builds we take
# the full-precision (fp32) one, for the same reason as the acoustic model: onnxruntime
# converts an fp16 build back to fp32 on a CPU anyway. The labels must come from the same
# release, since their rows line up with the model's output classes. The version is
# pinned rather than resolved from the releases API: a new model changes which species
# the station can report, and a label layout we no longer parse would empty the filter
# without saying so. Moving to a new release means editing the tag, both names, and both
# sizes together, after checking that GeoModel still reads it.
_RELEASE = "https://github.com/birdnet-team/geomodel/releases/download/v3.0.4"
_MODEL_NAME = "BirdNET+_Geomodel_V3.0.4_Global_14K_FP32.onnx"
_LABELS_NAME = "BirdNET+_Geomodel_V3.0.4_Global_14K_Labels.txt"

GEOMODEL_MODEL_URL = f"{_RELEASE}/{quote(_MODEL_NAME)}"
GEOMODEL_LABELS_URL = f"{_RELEASE}/{quote(_LABELS_NAME)}"
# The published byte sizes. A local file of the right size is taken to be the current one
# and is not downloaded again.
GEOMODEL_MODEL_SIZE = 15503473
GEOMODEL_LABELS_SIZE = 671823

_DOWNLOAD_TIMEOUT_SECONDS = 300
_CHUNK_SIZE = 1024 * 1024


def download_file(url: str, destination: Path) -> None:
    """
    Stream a release asset to destination.

    It downloads to a temporary file alongside the destination and then moves it into
    place in one step. Nobody ever reads a half-written file, and a download that fails
    partway leaves the previous copy where it was.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial_destination = destination.with_name(destination.name + ".part")

    logger.info("Downloading %s from GitHub", destination.name)
    try:
        with requests.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            with open(partial_destination, "wb") as output_file:
                for chunk in response.iter_content(_CHUNK_SIZE):
                    output_file.write(chunk)
        os.replace(partial_destination, destination)
    finally:
        partial_destination.unlink(missing_ok=True)
