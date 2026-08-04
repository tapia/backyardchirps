import hashlib
from pathlib import Path

from backyardchirps.shared.checksums import git_blob_sha1_of
from backyardchirps.shared.checksums import sha256_of


def test_sha256_of_matches_hashlib(tmp_path: Path) -> None:
    target = tmp_path / "model.onnx"
    target.write_bytes(b"perch weights")

    assert sha256_of(target) == hashlib.sha256(b"perch weights").hexdigest()


def test_git_blob_sha1_of_matches_the_known_git_object_id(tmp_path: Path) -> None:
    # `printf 'hello' | git hash-object --stdin` returns this id. Hard-coding it
    # pins the header format the Hugging Face listing is compared against.
    target = tmp_path / "labels.txt"
    target.write_bytes(b"hello")

    assert git_blob_sha1_of(target) == "b6fc4c620b67d95f953a5c1c1230aaab5db5a1b0"


def test_git_blob_sha1_of_reads_files_larger_than_one_chunk(tmp_path: Path) -> None:
    content = b"a" * (3 * 1024 * 1024 + 17)
    target = tmp_path / "big.bin"
    target.write_bytes(content)

    expected = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
    assert git_blob_sha1_of(target) == expected
