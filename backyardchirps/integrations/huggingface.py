import logging
import os
from dataclasses import dataclass
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# GeoModel 3 is published here as a flat set of files: the ONNX model and its labels.
_REPO_ID = "tphakala/BirdNET-Geomodel"
_TREE_URL = f"https://huggingface.co/api/models/{_REPO_ID}/tree/main"
_DOWNLOAD_URL = f"https://huggingface.co/{_REPO_ID}/resolve/main"
_LISTING_TIMEOUT_SECONDS = 30
_DOWNLOAD_TIMEOUT_SECONDS = 300
_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class RemoteFile:
    """
    One file published in the model repository.

    The Hub reports a digest of the content, so a caller can tell whether its local copy
    is current without downloading anything. Every file has a `git_blob_sha1`, and the
    ones kept in Git LFS, meaning the large ones, also have a `sha256`. Either identifies
    the content exactly.
    """

    path: str
    size: int
    sha256: str | None
    git_blob_sha1: str


def list_files() -> dict[str, RemoteFile]:
    """
    Every file published at the repository root, keyed by file name.
    """
    response = requests.get(_TREE_URL, timeout=_LISTING_TIMEOUT_SECONDS)
    response.raise_for_status()

    files: dict[str, RemoteFile] = {}
    for entry in response.json():
        if entry.get("type") != "file":
            continue
        remote_path = entry["path"]
        lfs_metadata = entry.get("lfs") or {}
        file_name = remote_path.rsplit("/", 1)[-1]
        files[file_name] = RemoteFile(
            path=remote_path,
            size=entry.get("size", 0),
            sha256=lfs_metadata.get("oid"),
            git_blob_sha1=entry["oid"],
        )
    return files


def download_file(remote_path: str, destination: Path) -> None:
    """
    Stream a repository file to destination.

    It downloads to a temporary file alongside the destination and then moves it into
    place in one step. Nobody ever reads a half-written file, and a download that fails
    partway leaves the previous copy where it was.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial_destination = destination.with_name(destination.name + ".part")

    logger.info("Downloading %s from Hugging Face", remote_path)
    try:
        with requests.get(
            f"{_DOWNLOAD_URL}/{remote_path}",
            stream=True,
            timeout=_DOWNLOAD_TIMEOUT_SECONDS,
        ) as response:
            response.raise_for_status()
            with open(partial_destination, "wb") as output_file:
                for chunk in response.iter_content(_CHUNK_SIZE):
                    output_file.write(chunk)
        os.replace(partial_destination, destination)
    finally:
        partial_destination.unlink(missing_ok=True)
