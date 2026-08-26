"""
Read the file the two privileged scripts write while they run.

Written by bash as root and read by Python as the service user, so nothing but a test joins
the two ends. What matters most here is that a station whose status file is damaged or absent
reads as idle rather than raising: the page that would show the error is the same page an
admin opens to find out what is wrong.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from backyardchirps.features.updates.entity import UpdateState
from backyardchirps.features.updates.entity import UpdateStep
from backyardchirps.features.updates.progress import read_progress

RUNNING = {
    "state": "running",
    "version": "0.3.0",
    "step": "installing",
    "message": "Installing 0.3.0",
    "updated_at": "20260826T091500Z",
}


@pytest.fixture(autouse=True)
def update_dir(tmp_path: Path, settings: Any) -> Path:
    settings.DATA_DIR = tmp_path
    (tmp_path / "update").mkdir()
    return tmp_path / "update"


def write(update_dir: Path, body: object) -> None:
    (update_dir / "status.json").write_text(body if isinstance(body, str) else json.dumps(body))


def test_a_station_that_has_never_updated_is_idle() -> None:
    assert read_progress().state is UpdateState.IDLE


def test_a_run_in_progress_is_read_back_whole(update_dir: Path) -> None:
    write(update_dir, RUNNING)

    progress = read_progress()

    assert progress.is_running
    assert progress.version == "0.3.0"
    assert progress.step is UpdateStep.INSTALLING
    assert progress.updated_at == "20260826T091500Z"


def test_the_stamp_is_what_separates_two_runs_that_end_the_same_way(update_dir: Path) -> None:
    """
    The bug this field was added for. A station that updates to a version, goes back, and
    updates to it again writes every other field identically both times.
    """
    finished = {**RUNNING, "state": "succeeded", "step": "finished", "message": "Now running 0.3.0"}
    write(update_dir, finished)
    first = read_progress()

    write(update_dir, {**finished, "updated_at": "20260826T104500Z"})
    second = read_progress()

    assert first.updated_at != second.updated_at
    assert (first.state, first.version, first.step, first.message) == (
        second.state,
        second.version,
        second.step,
        second.message,
    )


def test_a_station_whose_updater_does_not_stamp_the_file_still_reads(update_dir: Path) -> None:
    """
    An older updater, mid-upgrade: dpkg has replaced the code but the file on disk was
    written by the version before it.
    """
    write(update_dir, {key: value for key, value in RUNNING.items() if key != "updated_at"})

    progress = read_progress()

    assert progress.is_running
    assert progress.updated_at == ""


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("this is not json", id="a-file-that-is-not-json"),
        pytest.param('["a", "list"]', id="json-that-is-not-an-object"),
    ],
)
def test_a_damaged_file_reads_as_idle_rather_than_raising(update_dir: Path, body: str) -> None:
    write(update_dir, body)

    assert read_progress().state is UpdateState.IDLE


def test_a_state_this_version_has_never_heard_of_reads_as_idle(update_dir: Path) -> None:
    """
    The web process can be a version behind the script that wrote this, since dpkg replaces
    the files while the old process is still serving.
    """
    write(update_dir, {**RUNNING, "state": "reticulating"})

    assert read_progress().state is UpdateState.IDLE
