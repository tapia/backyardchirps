import dataclasses
import json
import logging
from pathlib import Path

from django.conf import settings

from backyardchirps.features.updates.entity import UpdateCheckResult

logger = logging.getLogger(__name__)

RESULT_FILE_NAME = "available.json"

# What a station knows before its first check has ever run, and what it falls back to when
# the file is missing or unreadable. Answering "no update" is the safe way to be wrong.
NOTHING_FOUND = UpdateCheckResult(version="", released="", changelog_url="", update_available=False, error="")


def result_path() -> Path:
    return Path(settings.DATA_DIR) / "update" / RESULT_FILE_NAME


def read_result() -> UpdateCheckResult | None:
    """
    What the privileged check last wrote, or None on a station where it has never run.

    Root writes this file and the service user only reads it, which is the same trust
    boundary the progress file has: the web process cannot write the directory, so it
    cannot put anything here for the rest of the application to believe.
    """
    path = result_path()
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logger.warning("Could not read the update check result at %s", path)
        return dataclasses.replace(NOTHING_FOUND, error="unreadable_result")

    if not isinstance(raw, dict):
        return dataclasses.replace(NOTHING_FOUND, error="unreadable_result")

    return UpdateCheckResult(
        version=str(raw.get("version", "")),
        released=str(raw.get("released", "")),
        changelog_url=str(raw.get("changelog_url", "")),
        update_available=bool(raw.get("update_available", False)),
        error=str(raw.get("error", "")),
    )
