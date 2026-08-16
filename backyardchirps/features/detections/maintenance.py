import logging

from django.conf import settings

from backyardchirps.features.detections import queries as detection_queries
from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.shared import disk_usage

logger = logging.getLogger(__name__)

_BATCH_SIZE = 20


def enforce_quota() -> int:
    """
    Delete the oldest clips until the disk is back under the configured quota, and return
    how many went. Only the audio files are deleted: every detection keeps its row, and
    so stays in the history without a recording to play.
    """
    clips_dir = settings.CLIPS["save_dir"]
    quota = Settings.get(SettingsKey.CLIPS_MAX_DISK_USAGE_PERCENT)
    deleted_count = 0

    while disk_usage.get_usage_percent(clips_dir) > quota:
        candidates = detection_queries.get_oldest_clips(_BATCH_SIZE)
        if not candidates:
            break
        for candidate in candidates:
            AudioClip.delete_clip(candidate["clip_path"])
            detection_queries.clear_clip_path(candidate["id"])
            deleted_count += 1

    logger.info(
        "Clip disk quota: deleted %d clip(s), usage now %.1f%%",
        deleted_count,
        disk_usage.get_usage_percent(clips_dir),
    )
    return deleted_count
