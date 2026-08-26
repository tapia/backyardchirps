"""
Read the file the privileged check writes.

The file is written by bash as root and read by Python as the service user, so nothing but
a test connects the two. What matters here is that a station with no file, or a file that
has been damaged, answers "no update" rather than raising out of a page an admin opened.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from backyardchirps.features.updates.available import read_result

RESULT = {
    "version": "9.9.9",
    "released": "2026-08-23",
    "changelog_url": "https://example.com/releases/tag/v9.9.9",
    "update_available": True,
    "error": "",
}


@pytest.fixture(autouse=True)
def update_dir(tmp_path: Path, settings: Any) -> Path:
    settings.DATA_DIR = tmp_path
    (tmp_path / "update").mkdir()
    return tmp_path / "update"


def write(update_dir: Path, body: str) -> None:
    (update_dir / "available.json").write_text(body)


def test_a_station_where_the_check_has_never_run_reads_nothing() -> None:
    assert read_result() is None


def test_what_the_check_wrote_is_read_back(update_dir: Path) -> None:
    write(update_dir, json.dumps(RESULT))

    result = read_result()

    assert result is not None
    assert result.succeeded
    assert result.version == "9.9.9"
    assert result.released == "2026-08-23"
    assert result.changelog_url == RESULT["changelog_url"]
    assert result.update_available is True


def test_a_failed_check_is_read_as_a_failure(update_dir: Path) -> None:
    write(
        update_dir, json.dumps({**RESULT, "version": "", "update_available": False, "error": "unreachable_repository"})
    )

    result = read_result()

    assert result is not None
    assert not result.succeeded
    assert result.error == "unreachable_repository"
    assert result.version == ""


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("this is not json", id="a-file-that-is-not-json"),
        pytest.param('["a", "list"]', id="json-that-is-not-an-object"),
    ],
)
def test_a_damaged_file_offers_nothing(update_dir: Path, body: str) -> None:
    """
    Raising here would take the server status page down with it, and the page is where an
    admin would go to find out what is wrong.
    """
    write(update_dir, body)

    result = read_result()

    assert result is not None
    assert result.update_available is False
    assert result.error == "unreadable_result"


def test_a_file_missing_the_keys_we_read_offers_nothing(update_dir: Path) -> None:
    """
    The script and this reader are versioned together, but they are not upgraded in the
    same instant: dpkg unpacks the new script while the old web process is still running.
    """
    write(update_dir, json.dumps({"unexpected": "shape"}))

    result = read_result()

    assert result is not None
    assert result.version == ""
    assert result.update_available is False
