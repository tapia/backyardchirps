"""
Import what the privileged check found, and see what gets stored.

The check itself is a root-owned script talking to apt. What is under test here is the
workflow around it: the answer it left behind is stored, a failure is stored as one, and
neither raises out of a job that runs unattended from a timer.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from backyardchirps.features.updates import logic as updates_logic
from backyardchirps.features.updates import queries as updates_queries

pytestmark = pytest.mark.django_db

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


def checked(update_dir: Path, **fields: Any) -> None:
    (update_dir / "available.json").write_text(json.dumps({**RESULT, **fields}))


def test_a_station_that_has_never_checked_reports_nothing() -> None:
    assert updates_queries.last_check() is None


def test_what_the_check_found_is_stored_and_read_back(update_dir: Path) -> None:
    checked(update_dir)

    result = updates_logic.import_update_check()

    assert result.succeeded
    assert result.version == "9.9.9"
    assert result.released == "2026-08-23"
    assert result.changelog_url == RESULT["changelog_url"]
    assert result.update_available is True

    stored = updates_queries.last_check()
    assert stored is not None
    assert stored.version == "9.9.9"


def test_importing_twice_leaves_one_result(update_dir: Path) -> None:
    """
    A row per check would grow without bound on a station that runs one every day and is
    never looked at, and nothing reads any result but the newest.
    """
    checked(update_dir)
    updates_logic.import_update_check()
    checked(update_dir, version="9.9.10")
    updates_logic.import_update_check()

    stored = updates_queries.last_check()
    assert stored is not None
    assert stored.version == "9.9.10"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param("unreachable_repository", id="a-station-with-no-internet"),
        pytest.param("nothing_offered", id="a-repository-with-no-package-in-it"),
        pytest.param("no_source", id="a-station-that-was-never-given-a-source"),
    ],
)
def test_a_failed_check_is_stored_rather_than_raised(update_dir: Path, error: str) -> None:
    checked(update_dir, version="", update_available=False, error=error)

    result = updates_logic.import_update_check()

    assert not result.succeeded
    assert result.error == error
    assert result.version == ""


def test_a_failure_clears_the_version_an_earlier_check_found(update_dir: Path) -> None:
    """
    Showing a version found days ago beside "the check is failing" invites reading the
    first and ignoring the second, and the station cannot tell whether it is still the
    latest.
    """
    checked(update_dir)
    updates_logic.import_update_check()
    checked(update_dir, version="", update_available=False, error="unreachable_repository")
    updates_logic.import_update_check()

    stored = updates_queries.last_check()
    assert stored is not None
    assert stored.version == ""
    assert stored.error == "unreachable_repository"


def test_importing_with_no_file_at_all_is_recorded_as_a_failure() -> None:
    """
    The command runs straight after the script that writes the file, so no file means the
    script did not get that far. Storing nothing would leave yesterday's answer looking
    like today's.
    """
    result = updates_logic.import_update_check()

    assert not result.succeeded
    assert result.error == "check_never_ran"
