import json

from django.db import models

from backyardchirps.features.updates.entity import AvailableUpdate


class StoredUpdateCheck(models.Model):
    """
    The result of the last check for a new release. One row, replaced on every check.
    """

    checked_at = models.DateTimeField(auto_now=True)
    manifest = models.TextField(blank=True)
    error = models.TextField(blank=True)

    class Meta:
        verbose_name = "update check"

    def __str__(self) -> str:
        return f"checked {self.checked_at:%Y-%m-%d %H:%M}"

    def to_entity(self) -> AvailableUpdate:
        fields: dict[str, object] = {}
        if self.manifest:
            try:
                parsed = json.loads(self.manifest)
                if isinstance(parsed, dict):
                    fields = parsed
            except ValueError:
                pass

        error = self.error
        if self.manifest and not fields:
            error = error or "unreadable_manifest"

        return AvailableUpdate(
            checked_at=self.checked_at,
            version=str(fields.get("version", "")),
            released=str(fields.get("released", "")),
            changelog_url=str(fields.get("changelog_url", "")),
            error=error,
        )
