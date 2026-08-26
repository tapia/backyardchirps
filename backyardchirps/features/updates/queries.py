from backyardchirps.features.updates.entity import AvailableUpdate
from backyardchirps.features.updates.entity import UpdateCheckResult
from backyardchirps.models.update_check import StoredUpdateCheck
from backyardchirps.models.update_request import StoredUpdateRequest


def last_check() -> AvailableUpdate | None:
    """
    What the last check found, or None on a station that has never run one.
    """
    row = StoredUpdateCheck.objects.first()
    if row is None:
        return None
    return row.to_entity()


def record_result(result: UpdateCheckResult) -> AvailableUpdate:
    """
    Replace the stored result with what the privileged check found.

    One row, always. `checked_at` is auto_now, so saving is what stamps it.
    """
    row = StoredUpdateCheck.objects.first() or StoredUpdateCheck()
    row.version = result.version
    row.released = result.released
    row.changelog_url = result.changelog_url
    row.update_available = result.update_available
    row.error = result.error
    row.save()
    return row.to_entity()


def requested_version() -> str:
    """
    The version an admin last asked for, or empty if none ever has been.
    """
    row = StoredUpdateRequest.objects.first()
    return row.version if row is not None else ""


def request_version(version: str) -> None:
    """
    Record what to install. One row, replaced.
    """
    row = StoredUpdateRequest.objects.first() or StoredUpdateRequest()
    row.version = version
    row.save()
