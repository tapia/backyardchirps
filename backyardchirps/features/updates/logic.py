import logging

import requests
from django.conf import settings
from packaging.version import InvalidVersion
from packaging.version import Version

from backyardchirps.features.updates import queries as updates_queries
from backyardchirps.features.updates.entity import AvailableUpdate
from backyardchirps.features.updates.progress import read_progress
from backyardchirps.integrations import updates as updates_integration
from backyardchirps.integrations.systemd import start_unit

logger = logging.getLogger(__name__)

# Root-owned, and granted `start` alone in the sudoers policy install.sh writes.
UPDATE_UNIT = "backyardchirps-update"
ROLLBACK_UNIT = "backyardchirps-rollback"


def check_for_update() -> AvailableUpdate:
    """
    Fetch the release manifest and store what came back, or why it could not be fetched.
    """
    try:
        manifest = updates_integration.fetch_manifest()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Could not check for an update: %s", exc)
        return updates_queries.record_failure(type(exc).__name__)

    result = updates_queries.record_result(manifest)
    if is_newer_than_current_version(result.version):
        logger.info("Version %s is available, this station runs %s", result.version, settings.VERSION)
    return result


def is_newer_than_current_version(version: str) -> bool:
    """
    Check if a published version is newer than the one this station runs.
    """
    if not version:
        return False
    try:
        return Version(version) > Version(settings.VERSION)
    except InvalidVersion:
        logger.warning("Cannot compare published version %r with running version %r", version, settings.VERSION)
        return False


class UpdateRefused(Exception):
    """
    Why an update was not started. The message is a code the frontend translates.
    """


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
    if not is_newer_than_current_version(version):
        raise UpdateRefused("not_newer_than_running")

    updates_queries.request_version(version)
    if not start_unit(UPDATE_UNIT):
        raise UpdateRefused("could_not_start_updater")


def start_rollback() -> None:
    """
    Ask the station to go back to the release installed before this one.
    """
    if read_progress().is_running:
        raise UpdateRefused("update_already_running")
    if not start_unit(ROLLBACK_UNIT):
        raise UpdateRefused("could_not_start_updater")
