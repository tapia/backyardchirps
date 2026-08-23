from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True)
class AvailableUpdate:
    """
    What the last check found, and when it ran.
    """

    checked_at: datetime
    version: str
    released: str
    changelog_url: str
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
    """

    state: UpdateState
    version: str
    step: UpdateStep
    message: str

    @property
    def is_running(self) -> bool:
        return self.state is UpdateState.RUNNING
