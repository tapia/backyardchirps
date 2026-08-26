"""
What start_update refuses, and what it records when it agrees.

Every check here is a courtesy to the person clicking rather than a boundary: the updater
asks the repository again as root and refuses anything apt does not offer. These tests are
about not starting a root-owned unit for a request that is already known to be wrong.
"""

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from backyardchirps.features.updates import logic as updates_logic
from backyardchirps.features.updates import progress as updates_progress
from backyardchirps.features.updates import queries as updates_queries
from backyardchirps.features.updates.entity import UpdateCheckResult
from backyardchirps.features.updates.entity import UpdateState

pytestmark = pytest.mark.django_db

FOUND = UpdateCheckResult(
    version="9.9.9",
    released="2026-08-23",
    changelog_url="https://example.com/v9.9.9",
    update_available=True,
    error="",
)


@pytest.fixture(autouse=True)
def started_units(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """
    Nothing in this file may reach sudo. A test that starts the real unit would try to
    update the machine running the suite.
    """
    started: list[str] = []
    monkeypatch.setattr(updates_logic, "start_unit", lambda unit: started.append(unit) or True)
    return started


@pytest.fixture(autouse=True)
def status_dir(tmp_path: Path, settings: Any) -> Path:
    settings.DATA_DIR = tmp_path
    (tmp_path / "update").mkdir()
    return tmp_path / "update"


def offer(version: str = "9.9.9", update_available: bool = True) -> None:
    updates_queries.record_result(dataclasses.replace(FOUND, version=version, update_available=update_available))


def test_the_offered_version_starts_the_updater(settings: Any, started_units: list[str]) -> None:
    settings.VERSION = "0.2.0"
    offer()

    updates_logic.start_update("9.9.9")

    assert updates_queries.requested_version() == "9.9.9"
    assert started_units == [updates_logic.UPDATE_UNIT]


def test_a_version_that_was_never_offered_is_refused(settings: Any, started_units: list[str]) -> None:
    """
    The check that matters. Without it the web process would write any string an admin
    sent into a row that a root-owned unit reads.
    """
    settings.VERSION = "0.2.0"
    offer()

    with pytest.raises(updates_logic.UpdateRefused, match="version_not_offered"):
        updates_logic.start_update("6.6.6")

    assert updates_queries.requested_version() == ""
    assert started_units == []


def test_nothing_is_started_before_a_successful_check(settings: Any, started_units: list[str]) -> None:
    settings.VERSION = "0.2.0"

    with pytest.raises(updates_logic.UpdateRefused, match="no_successful_check"):
        updates_logic.start_update("9.9.9")

    assert started_units == []


def test_a_failed_check_offers_nothing(settings: Any, started_units: list[str]) -> None:
    settings.VERSION = "0.2.0"
    updates_queries.record_result(
        dataclasses.replace(FOUND, version="", update_available=False, error="unreachable_repository")
    )

    with pytest.raises(updates_logic.UpdateRefused, match="no_successful_check"):
        updates_logic.start_update("")

    assert started_units == []


def test_a_version_apt_does_not_call_an_update_is_refused(settings: Any, started_units: list[str]) -> None:
    """
    Installing the version already running would be a no-op that restarts the recorder for
    nothing. Which of two versions is newer is apt's answer, recorded by the check, so this
    reads that answer rather than working it out a second time and possibly differently.
    """
    settings.VERSION = "9.9.9"
    offer(update_available=False)

    with pytest.raises(updates_logic.UpdateRefused, match="not_newer_than_running"):
        updates_logic.start_update("9.9.9")

    assert started_units == []


def test_a_second_update_is_refused_while_one_runs(settings: Any, status_dir: Path, started_units: list[str]) -> None:
    settings.VERSION = "0.2.0"
    offer()
    (status_dir / "status.json").write_text(
        '{"state": "running", "version": "9.9.9", "step": "installing", "message": ""}'
    )

    with pytest.raises(updates_logic.UpdateRefused, match="update_already_running"):
        updates_logic.start_update("9.9.9")

    assert started_units == []


def test_a_finished_update_does_not_block_the_next_one(settings: Any, status_dir: Path) -> None:
    settings.VERSION = "0.2.0"
    offer()
    (status_dir / "status.json").write_text(
        '{"state": "succeeded", "version": "0.2.0", "step": "finished", "message": ""}'
    )

    updates_logic.start_update("9.9.9")

    assert updates_queries.requested_version() == "9.9.9"


def test_an_unreadable_status_file_is_not_treated_as_a_running_update(settings: Any, status_dir: Path) -> None:
    """
    A station whose status file is corrupt is not mid-update, and refusing every future
    update because of it would need a person with a shell to clear.
    """
    settings.VERSION = "0.2.0"
    offer()
    (status_dir / "status.json").write_text("this is not json")

    assert updates_progress.read_progress().state is UpdateState.IDLE
    updates_logic.start_update("9.9.9")
    assert updates_queries.requested_version() == "9.9.9"


def test_a_rollback_starts_the_privileged_unit(started_units: list[str]) -> None:
    """
    Nothing is checked here on purpose. Whether the packages to go back to were saved, and
    whether the database has moved past what that version understands, are both things only
    the rollback script can see, and it refuses rather than half-doing it.
    """
    updates_logic.start_rollback()

    assert started_units == [updates_logic.ROLLBACK_UNIT]


def test_a_rollback_is_refused_while_an_update_runs(status_dir: Path, started_units: list[str]) -> None:
    (status_dir / "status.json").write_text(
        '{"state": "running", "version": "9.9.9", "step": "installing", "message": ""}'
    )

    with pytest.raises(updates_logic.UpdateRefused, match="update_already_running"):
        updates_logic.start_rollback()

    assert started_units == []


def test_a_check_is_refused_while_an_update_runs(status_dir: Path, started_units: list[str]) -> None:
    """
    Both talk to apt, and apt takes a lock. A check started mid-update would sit waiting
    for it and hold the request open until it gave up.
    """
    (status_dir / "status.json").write_text(
        '{"state": "running", "version": "9.9.9", "step": "installing", "message": ""}'
    )

    with pytest.raises(updates_logic.UpdateRefused, match="update_already_running"):
        updates_logic.start_check()

    assert started_units == []
