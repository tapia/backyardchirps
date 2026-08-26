from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True)
class UpdateCheckResult:
    """
    What the privileged check found, as it wrote it down.

    `update_available` is apt's answer rather than one this station worked out. dpkg has
    already ordered the two versions and the install will obey that ordering, so anything
    computed here could only disagree with it.
    """

    version: str
    released: str
    changelog_url: str
    update_available: bool
    error: str

    @property
    def succeeded(self) -> bool:
        return not self.error


@dataclass(frozen=True)
class AvailableUpdate:
    """
    The stored result of the last check, and when it was stored.
    """

    checked_at: datetime
    version: str
    released: str
    changelog_url: str
    update_available: bool
    error: str

    @property
    def succeeded(self) -> bool:
        return not self.error


class UpdateState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class UpdateStep(StrEnum):
    NONE = ""
    CHECKING = "checking"
    # No longer written by anything here: the backup moved into the package's postinst,
    # which does not report progress. It stays because a station still on the tarball path
    # writes it, and an unknown step makes the reader log a warning on every poll. It goes
    # when deploy/ does.
    BACKING_UP = "backing-up"
    INSTALLING = "installing"
    VERIFYING = "verifying"
    ROLLING_BACK = "rolling-back"
    RESTORING = "restoring"
    FINISHED = "finished"


@dataclass(frozen=True)
class UpdateProgress:
    """
    What the updater is doing, as the status file reports it.

    `updated_at` is what tells one run from another. The station keeps the outcome of its
    last run until something replaces it, and two runs can end with the same words: a station
    updated to a version, put back, and updated to it again writes the same four other fields
    both times. Without the stamp a page watching the second run would take the first one's
    outcome for it.
    """

    state: UpdateState
    version: str
    step: UpdateStep
    message: str
    updated_at: str

    @property
    def is_running(self) -> bool:
        return self.state is UpdateState.RUNNING
