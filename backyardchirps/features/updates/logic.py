import logging

import requests
from django.conf import settings
from packaging.version import InvalidVersion
from packaging.version import Version

from backyardchirps.features.updates import queries as updates_queries
from backyardchirps.features.updates.entity import AvailableUpdate
from backyardchirps.integrations import updates as updates_integration

logger = logging.getLogger(__name__)


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
