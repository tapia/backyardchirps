"""
What start_update refuses, and what it records when it agrees.

Every check here is a courtesy to the person clicking rather than a boundary: the updater
re-reads the manifest as root and refuses anything it does not offer. These tests are
about not starting a root-owned unit for a request that is already known to be wrong.
"""

from pathlib import Path
from typing import Any

import pytest

from backyardchirps.features.updates import logic as updates_logic
from backyardchirps.features.updates import progress as updates_progress
from backyardchirps.features.updates import queries as updates_queries
from backyardchirps.features.updates.entity import UpdateState

pytestmark = pytest.mark.django_db

MANIFEST = {"version": "9.9.9", "released": "2026-08-23", "changelog_url": "https://example.com/v9.9.9"}


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


def offer(version: str = "9.9.9") -> None:
    updates_queries.record_result({**MANIFEST, "version": version})


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
    updates_queries.record_failure("ConnectionError")

    with pytest.raises(updates_logic.UpdateRefused, match="no_successful_check"):
        updates_logic.start_update("")

    assert started_units == []


def test_a_version_that_is_not_newer_is_refused(settings: Any, started_units: list[str]) -> None:
    """
    Installing the version already running would be a no-op that restarts the recorder
    and swaps the release for an identical one.
    """
    settings.VERSION = "9.9.9"
    offer()

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
    Nothing is checked here on purpose. Whether an earlier release is still on disk, and
    whether the database has moved past what it understands, are both things only
    rollback.sh can see, and it refuses rather than half-doing it.
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
