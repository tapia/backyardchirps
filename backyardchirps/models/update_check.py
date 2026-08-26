from django.db import models

from backyardchirps.features.updates.entity import AvailableUpdate


class StoredUpdateCheck(models.Model):
    """
    The result of the last check for a newer version. One row, replaced on every check.

    The fields are the answer itself rather than a copy of what a server said, which is
    what the manifest column used to hold. apt decides whether a version is newer, so
    `update_available` is stored rather than worked out again every time it is read.
    """

    checked_at = models.DateTimeField(auto_now=True)
    version = models.CharField(max_length=100, blank=True)
    released = models.CharField(max_length=100, blank=True)
    changelog_url = models.URLField(max_length=500, blank=True)
    update_available = models.BooleanField(default=False)
    error = models.TextField(blank=True)

    class Meta:
        verbose_name = "update check"

    def __str__(self) -> str:
        return f"checked {self.checked_at:%Y-%m-%d %H:%M}"

    def to_entity(self) -> AvailableUpdate:
        return AvailableUpdate(
            checked_at=self.checked_at,
            version=self.version,
            released=self.released,
            changelog_url=self.changelog_url,
            update_available=self.update_available,
            error=self.error,
        )
