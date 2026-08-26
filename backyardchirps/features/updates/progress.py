import json
import logging
from pathlib import Path

from django.conf import settings

from backyardchirps.features.updates.entity import UpdateProgress
from backyardchirps.features.updates.entity import UpdateState
from backyardchirps.features.updates.entity import UpdateStep

logger = logging.getLogger(__name__)

STATUS_FILE_NAME = "status.json"

IDLE = UpdateProgress(state=UpdateState.IDLE, version="", step=UpdateStep.NONE, message="", updated_at="")


def status_path() -> Path:
    return Path(settings.DATA_DIR) / "update" / STATUS_FILE_NAME


def read_progress() -> UpdateProgress:
    path = status_path()
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        return IDLE
    except (OSError, ValueError):
        logger.warning("Could not read the update status at %s", path)
        return IDLE

    if not isinstance(raw, dict):
        return IDLE

    return UpdateProgress(
        state=_parse_state(raw.get("state")),
        version=str(raw.get("version", "")),
        step=_parse_step(raw.get("step")),
        message=str(raw.get("message", "")),
        # Empty on a station whose updater is older than this field. The page falls back to
        # what it can see rather than waiting for a stamp that will never come.
        updated_at=str(raw.get("updated_at", "")),
    )


def _parse_state(value: object) -> UpdateState:
    try:
        return UpdateState(str(value))
    except ValueError:
        logger.warning("The update status holds the state %r, which this version does not know", value)
        return UpdateState.IDLE


def _parse_step(value: object) -> UpdateStep:
    try:
        return UpdateStep(str(value))
    except ValueError:
        logger.warning("The update status holds the step %r, which this version does not know", value)
        return UpdateStep.NONE
