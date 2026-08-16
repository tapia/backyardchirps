"""
Where an install reports how far it has got.

A file rather than something in memory, for two reasons. The web process runs two workers,
so the request that starts an install and the request that asks about it are usually not
in the same process. And an install outlives the page that asked for it: a pack takes
minutes on a Pi at the end of a garden, and a phone that locks its screen must not cost
somebody the download.
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from enum import StrEnum
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# How long a running install may go without saying anything before it is taken to be
# dead. Progress is written far more often than this; only a worker killed mid-download
# leaves a file that stops changing.
_SILENCE_BEFORE_ABANDONED_SECONDS = 120.0

# Progress is written at most this often. A pack arrives in one-megabyte chunks, so
# without this a download would write the file a few hundred times for a bar that moves
# in steps nobody can see.
_WRITE_EVERY_SECONDS = 0.5


class InstallState(StrEnum):
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class InstallProgress:
    state: InstallState
    pack_id: str
    received_bytes: int
    total_bytes: int
    error: str

    @property
    def fraction(self) -> float | None:
        """
        How far along, from 0 to 1, or None when the size is not known yet.
        """
        if self.total_bytes <= 0:
            return None
        return min(1.0, self.received_bytes / self.total_bytes)


def read() -> InstallProgress | None:
    """
    The current install, or None when nothing has ever been started here.

    An install that has said nothing for a long time is reported as failed. The
    alternative is a progress bar that sits still for ever because the worker carrying it
    was killed.
    """
    path = _path()
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    progress = InstallProgress(
        state=InstallState(stored.get("state", InstallState.FAILED)),
        pack_id=str(stored.get("pack_id", "")),
        received_bytes=int(stored.get("received_bytes", 0)),
        total_bytes=int(stored.get("total_bytes", 0)),
        error=str(stored.get("error", "")),
    )
    if progress.state is InstallState.RUNNING and _silent_for(stored) > _SILENCE_BEFORE_ABANDONED_SECONDS:
        return InstallProgress(
            state=InstallState.FAILED,
            pack_id=progress.pack_id,
            received_bytes=progress.received_bytes,
            total_bytes=progress.total_bytes,
            error="interrupted",
        )
    return progress


def is_running() -> bool:
    progress = read()
    return progress is not None and progress.state is InstallState.RUNNING


def started(pack_id: str, total_bytes: int) -> None:
    _write(InstallState.RUNNING, pack_id, 0, total_bytes, "")


def progressed(pack_id: str, received_bytes: int, total_bytes: int) -> None:
    """
    Report how much has arrived, no more often than the write interval.
    """
    global _last_written_at

    now = _now()
    if now - _last_written_at < _WRITE_EVERY_SECONDS:
        return
    _last_written_at = now
    _write(InstallState.RUNNING, pack_id, received_bytes, total_bytes, "")


def finished(pack_id: str) -> None:
    _write(InstallState.DONE, pack_id, 0, 0, "")


def failed(pack_id: str, error: str) -> None:
    _write(InstallState.FAILED, pack_id, 0, 0, error)


def clear() -> None:
    _path().unlink(missing_ok=True)


_last_written_at = 0.0


def _path() -> Path:
    return Path(settings.REGION_PACK_INSTALL_STATUS_FILE)


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


def _silent_for(stored: dict[str, object]) -> float:
    try:
        updated = float(str(stored.get("updated_at", 0)))
    except ValueError:
        return 0.0
    return _now() - updated


def _write(state: InstallState, pack_id: str, received_bytes: int, total_bytes: int, error: str) -> None:
    """
    Replace the status file in one step, so a reader never catches it half written.
    """
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    partial.write_text(
        json.dumps(
            {
                "state": str(state),
                "pack_id": pack_id,
                "received_bytes": received_bytes,
                "total_bytes": total_bytes,
                "error": error,
                "updated_at": _now(),
            }
        ),
        encoding="utf-8",
    )
    os.replace(partial, path)
