import dataclasses
import logging

from backyardchirps.features.updates import queries as updates_queries
from backyardchirps.features.updates.available import NOTHING_FOUND
from backyardchirps.features.updates.available import read_result
from backyardchirps.features.updates.entity import AvailableUpdate
from backyardchirps.features.updates.progress import read_progress
from backyardchirps.integrations.systemd import start_unit

logger = logging.getLogger(__name__)

# Root-owned, and granted `start` alone in the sudoers policy the package ships.
UPDATE_UNIT = "backyardchirps-update"
ROLLBACK_UNIT = "backyardchirps-rollback"
CHECK_UNIT = "backyardchirps-check-update"


def import_update_check() -> AvailableUpdate:
    """
    Store what the privileged check wrote down, replacing whatever was there before.

    The station never talks to the repository from this process. Reading it needs root, so
    the check runs as a unit, writes its answer to a file the web process cannot write, and
    this puts that answer in the database.
    """
    result = read_result()
    if result is None:
        logger.warning("There is no check result to import, so the check cannot have run.")
        result = dataclasses.replace(NOTHING_FOUND, error="check_never_ran")
    return updates_queries.record_result(result)


class UpdateRefused(Exception):
    """
    Why an update was not started. The message is a code the frontend translates.
    """


def start_check() -> None:
    """
    Ask the station to look at the repository now, rather than waiting for the daily timer.
    """
    if read_progress().is_running:
        raise UpdateRefused("update_already_running")
    if not start_unit(CHECK_UNIT):
        raise UpdateRefused("could_not_start_check")


def start_update(version: str) -> None:
    """
    Record the version to install and ask the privileged unit to run.
    """
    if read_progress().is_running:
        raise UpdateRefused("update_already_running")

    last = updates_queries.last_check()
    if last is None or not last.succeeded:
        raise UpdateRefused("no_successful_check")
    if version != last.version:
        raise UpdateRefused("version_not_offered")
    if not last.update_available:
        raise UpdateRefused("not_newer_than_running")

    updates_queries.request_version(version)
    if not start_unit(UPDATE_UNIT):
        raise UpdateRefused("could_not_start_updater")


def start_rollback() -> None:
    """
    Ask the station to go back to the version running before the last update.
    """
    if read_progress().is_running:
        raise UpdateRefused("update_already_running")
    if not start_unit(ROLLBACK_UNIT):
        raise UpdateRefused("could_not_start_updater")
