import json
from typing import Any

from backyardchirps.features.updates.entity import AvailableUpdate
from backyardchirps.models.update_check import StoredUpdateCheck


def last_check() -> AvailableUpdate | None:
    """
    What the last check found, or None on a station that has never run one.
    """
    row = StoredUpdateCheck.objects.first()
    if row is None:
        return None
    return row.to_entity()


def record_result(manifest: dict[str, Any]) -> AvailableUpdate:
    """
    Replace the stored result with a manifest that came back.
    """
    return _store(manifest=json.dumps(manifest), error="")


def record_failure(error: str) -> AvailableUpdate:
    """
    Replace the stored result with the reason the check could not run.
    """
    return _store(manifest="", error=error)


def _store(manifest: str, error: str) -> AvailableUpdate:
    """
    One row, always. `checked_at` is auto_now, so saving is what stamps it.
    """
    row = StoredUpdateCheck.objects.first() or StoredUpdateCheck()
    row.manifest = manifest
    row.error = error
    row.save()
    return row.to_entity()
