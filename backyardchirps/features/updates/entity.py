from dataclasses import dataclass
from datetime import datetime


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
