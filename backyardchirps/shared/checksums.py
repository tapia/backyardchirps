import hashlib
from pathlib import Path
from typing import Any

_CHUNK_SIZE = 1024 * 1024


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    _feed(digest, path)
    return digest.hexdigest()


def git_blob_sha1_of(path: Path) -> str:
    """
    The git object id of a file: the SHA-1 of the header "blob <size>", a NUL byte, and
    then the content. Git hosts publish this id for files they do not keep in Git LFS,
    so a local file can be compared against a listing without downloading anything.
    """
    header = f"blob {path.stat().st_size}\0".encode()
    digest = hashlib.sha1(header)
    _feed(digest, path)
    return digest.hexdigest()


def _feed(digest: Any, path: Path) -> None:
    with open(path, "rb") as source_file:
        for chunk in iter(lambda: source_file.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
