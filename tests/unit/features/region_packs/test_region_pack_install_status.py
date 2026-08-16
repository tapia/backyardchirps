"""
The file an install reports progress through.

A file rather than memory, because the two web workers do not share any, and because an
install outlives the page that started it.
"""

from pathlib import Path
from typing import Any

import pytest

from backyardchirps.features.region_packs import install_status
from backyardchirps.features.region_packs.install_status import InstallState


@pytest.fixture(autouse=True)
def status_file(tmp_path: Path, settings: Any) -> Path:
    settings.REGION_PACK_INSTALL_STATUS_FILE = tmp_path / "pack-install-status.json"
    install_status._last_written_at = 0.0
    return tmp_path / "pack-install-status.json"


def test_nothing_has_been_installed_yet(status_file: Path) -> None:
    assert install_status.read() is None
    assert install_status.is_running() is False


def test_a_started_install_is_running(status_file: Path) -> None:
    install_status.started("iberian-peninsula", 180_000_000)

    progress = install_status.read()

    assert progress is not None
    assert progress.state is InstallState.RUNNING
    assert progress.total_bytes == 180_000_000
    assert install_status.is_running() is True


def test_progress_is_reported_as_a_fraction(status_file: Path) -> None:
    install_status.started("iberian-peninsula", 100)
    install_status._last_written_at = 0.0
    install_status.progressed("iberian-peninsula", 25, 100)

    progress = install_status.read()

    assert progress is not None
    assert progress.fraction == 0.25


def test_a_size_nobody_knows_has_no_fraction(status_file: Path) -> None:
    """
    A server that sends no Content-Length gives a bar with nothing to draw, which is a
    bar that should say it does not know rather than one stuck at zero.
    """
    install_status.started("iberian-peninsula", 0)

    progress = install_status.read()

    assert progress is not None
    assert progress.fraction is None


def test_finishing_and_failing_are_both_final(status_file: Path) -> None:
    install_status.started("iberian-peninsula", 100)
    install_status.finished("iberian-peninsula")
    assert install_status.is_running() is False

    install_status.failed("iberian-peninsula", "checksum")
    failure = install_status.read()
    assert failure is not None
    assert failure.state is InstallState.FAILED
    assert failure.error == "checksum"


def test_an_install_that_has_gone_quiet_is_reported_as_failed(status_file: Path, monkeypatch: Any) -> None:
    """
    A worker killed mid-download leaves a file saying "running" that never changes again.
    Without this the page watching it would show a bar that never moves and never ends.
    """
    install_status.started("iberian-peninsula", 100)
    later = install_status._now() + install_status._SILENCE_BEFORE_ABANDONED_SECONDS + 1
    monkeypatch.setattr(install_status, "_now", lambda: later)

    progress = install_status.read()

    assert progress is not None
    assert progress.state is InstallState.FAILED
    assert progress.error == "interrupted"


def test_progress_is_not_written_on_every_chunk(status_file: Path) -> None:
    """
    A pack arrives in one-megabyte pieces, so a few hundred writes would buy a bar that
    moves in steps nobody can see.
    """
    install_status.started("iberian-peninsula", 100)
    install_status.progressed("iberian-peninsula", 10, 100)
    install_status.progressed("iberian-peninsula", 20, 100)

    progress = install_status.read()

    assert progress is not None
    assert progress.received_bytes == 10
