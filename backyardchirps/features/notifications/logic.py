import asyncio
import logging
from abc import ABC
from abc import abstractmethod
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from aiogram.types import BufferedInputFile
from aiogram.types import URLInputFile
from django.utils import timezone
from django.utils import translation
from django.utils.translation import gettext as _

from backyardchirps.features.detections import queries as detection_queries
from backyardchirps.features.detections.entity import Detection
from backyardchirps.features.overrides import queries as override_queries
from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.integrations.telegram import send_photo_and_audio

logger = logging.getLogger(__name__)


class NotificationRule(ABC):
    """
    One reason to send a Telegram notification. A subclass decides when a detection is
    worth sending and what line it adds to the message.

    Several rules can match the same detection, and then the message carries all of
    their labels.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Short identifier for the logs. Never shown to the user.
        """

    @abstractmethod
    def should_notify(self, detection: Detection) -> bool: ...

    @abstractmethod
    def build_label(self, language: str) -> str:
        """
        The label this rule adds to the message, translated. For example
        "First detection today".
        """


class NewSpeciesRule(NotificationRule):
    """
    Fires the first time a species is ever detected.
    """

    @property
    def name(self) -> str:
        return "new_species"

    def should_notify(self, detection: Detection) -> bool:
        if not Settings.get(SettingsKey.NOTIFICATIONS_NEW_SPECIES_ENABLED):
            return False
        min_confidence = Settings.get(SettingsKey.NOTIFICATIONS_NEW_SPECIES_CONFIDENCE)
        if detection.confidence < min_confidence:
            return False
        return not detection_queries.has_detection_before(detection.species, detection.recorded_at)

    def build_label(self, language: str) -> str:
        with translation.override(language):
            return _("New species")


class FirstDetectionTodayRule(NotificationRule):
    """
    Fires once a day per species, on the first detection confident enough to count.
    """

    @property
    def name(self) -> str:
        return "first_detection_today"

    def should_notify(self, detection: Detection) -> bool:
        if not Settings.get(SettingsKey.NOTIFICATIONS_FIRST_TODAY_ENABLED):
            return False
        min_confidence = Settings.get(SettingsKey.NOTIFICATIONS_FIRST_TODAY_CONFIDENCE)
        if detection.confidence < min_confidence:
            return False
        local_dt = timezone.localtime(detection.recorded_at)
        today_start = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return not detection_queries.has_detection_in_range(
            detection.species, today_start, detection.recorded_at, min_confidence
        )

    def build_label(self, language: str) -> str:
        with translation.override(language):
            return _("First detection today")


class RareSpeciesRule(NotificationRule):
    """
    Fires once a day for a species that is not expected in the local area.
    """

    @property
    def name(self) -> str:
        return "rare_species"

    def should_notify(self, detection: Detection) -> bool:
        if not Settings.get(SettingsKey.NOTIFICATIONS_RARE_ENABLED):
            return False
        min_confidence = Settings.get(SettingsKey.NOTIFICATIONS_RARE_CONFIDENCE)
        if detection.confidence < min_confidence:
            return False
        if detection.species.is_rare() is not True:
            return False
        local_dt = timezone.localtime(detection.recorded_at)
        today_start = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return not detection_queries.has_detection_in_range(
            detection.species, today_start, detection.recorded_at, min_confidence
        )

    def build_label(self, language: str) -> str:
        with translation.override(language):
            return _("Rare species")


class FirstDetectionThisYearRule(NotificationRule):
    """
    Fires once a calendar year per species, on the first detection confident enough to
    count.
    """

    @property
    def name(self) -> str:
        return "first_detection_this_year"

    def should_notify(self, detection: Detection) -> bool:
        if not Settings.get(SettingsKey.NOTIFICATIONS_FIRST_YEAR_ENABLED):
            return False
        min_confidence = Settings.get(SettingsKey.NOTIFICATIONS_FIRST_YEAR_CONFIDENCE)
        if detection.confidence < min_confidence:
            return False
        local_dt = timezone.localtime(detection.recorded_at)
        year_start = local_dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        return not detection_queries.has_detection_in_range(
            detection.species, year_start, detection.recorded_at, min_confidence
        )

    def build_label(self, language: str) -> str:
        with translation.override(language):
            return _("First of the year")


class LongAbsentSpeciesRule(NotificationRule):
    """
    Fires when a species comes back after being away longer than the configured number
    of days.
    """

    @property
    def name(self) -> str:
        return "long_absent_species"

    def should_notify(self, detection: Detection) -> bool:
        if not Settings.get(SettingsKey.NOTIFICATIONS_LONG_ABSENT_ENABLED):
            return False
        min_confidence = Settings.get(SettingsKey.NOTIFICATIONS_LONG_ABSENT_CONFIDENCE)
        if detection.confidence < min_confidence:
            return False
        absence_days = Settings.get(SettingsKey.NOTIFICATIONS_LONG_ABSENT_DAYS)
        absence_cutoff = detection.recorded_at - timedelta(days=absence_days)
        if not detection_queries.has_detection_before(detection.species, absence_cutoff):
            return False
        return not detection_queries.has_detection_in_range(
            detection.species, absence_cutoff, detection.recorded_at, min_confidence
        )

    def build_label(self, language: str) -> str:
        absence_days = Settings.get(SettingsKey.NOTIFICATIONS_LONG_ABSENT_DAYS)
        with translation.override(language):
            return _("Not seen for %(days)s days") % {"days": absence_days}


class PendingValidationRule(NotificationRule):
    """
    Fires for every detection that lands in the review queue instead of being confirmed
    on its own.
    """

    @property
    def name(self) -> str:
        return "pending_validation"

    def should_notify(self, detection: Detection) -> bool:
        if not Settings.get(SettingsKey.NOTIFICATIONS_PENDING_VALIDATION_ENABLED):
            return False
        return detection.is_pending_validation()

    def build_label(self, language: str) -> str:
        with translation.override(language):
            return _("Dubious identification, pending human validation")


_RULES: list[NotificationRule] = [
    NewSpeciesRule(),
    FirstDetectionThisYearRule(),
    RareSpeciesRule(),
    LongAbsentSpeciesRule(),
    FirstDetectionTodayRule(),
    PendingValidationRule(),
]


class Notifier:
    def __init__(self) -> None:
        self._pending_notifications: dict[int, tuple[Detection, AudioClip]] = {}

    def maybe_notify(self, detection: Detection, clip: AudioClip) -> None:
        self._pending_notifications[detection.id] = (detection, clip)

    def flush(self, current_block_time: datetime) -> None:
        """
        Send the notifications for every detection whose time block has closed.

        Called once per clip, before that clip is processed. A detection waits here until
        the recorder has moved on to a later block, because only then can we be sure its
        confidence will not be raised again.
        """
        closed_pks = [
            pk
            for pk, (detection, _) in self._pending_notifications.items()
            if detection.recorded_at < current_block_time
        ]

        for pk in closed_pks:
            detection, clip = self._pending_notifications.pop(pk)
            self._evaluate_and_send(detection, clip)

    def _evaluate_and_send(self, detection: Detection, clip: AudioClip) -> None:
        # Read on every send rather than at startup, so that setting the credentials in
        # the wizard turns notifications on without restarting the recorder.
        token = Settings.get(SettingsKey.TELEGRAM_TOKEN)
        chat_id = Settings.get(SettingsKey.TELEGRAM_CHAT_ID)
        if not token or not chat_id:
            return
        if override_queries.is_blacklisted(detection.species):
            return
        language = Settings.get(SettingsKey.NOTIFICATIONS_LANGUAGE)
        matching_labels: list[str] = []
        for rule in _RULES:
            if rule.should_notify(detection):
                logger.info(
                    "Rule '%s' matched for %s (%.0f%%)",
                    rule.name,
                    detection.species.scientific_name,
                    detection.confidence * 100,
                )
                matching_labels.append(rule.build_label(language))
        if matching_labels:
            caption = self._build_caption(detection, matching_labels, language)
            audio_bytes, audio_filename = self._read_audio(detection, clip)
            asyncio.run(self._send_all(token, chat_id, detection, caption, audio_bytes, audio_filename))

    async def _send_all(
        self,
        token: str,
        chat_id: str,
        detection: Detection,
        caption: str,
        audio_bytes: bytes,
        audio_filename: str,
    ) -> None:
        species = detection.species
        photo = (
            BufferedInputFile(species.image_path.read_bytes(), filename=species.image_path.name)
            if species.image_path
            else URLInputFile(species.image_url)
        )
        audio = BufferedInputFile(audio_bytes, filename=audio_filename)
        await send_photo_and_audio(
            token,
            chat_id,
            photo,
            caption,
            audio,
        )
        logger.info("Telegram notification sent for %s", species.scientific_name)

    @staticmethod
    def _read_audio(detection: Detection, clip: AudioClip) -> tuple[bytes, str]:
        recorded_at_str = detection.recorded_at.strftime("%Y%m%d_%H%M%S")
        safe_name = detection.species.scientific_name.replace(" ", "_")
        filename = f"{recorded_at_str}_{safe_name}.wav"
        if detection.clip_path:
            return Path(detection.clip_path).read_bytes(), filename
        with clip.as_wav() as wav_path:
            return wav_path.read_bytes(), filename

    def _build_caption(self, detection: Detection, labels: list[str], language: str) -> str:
        with translation.override(language):
            common = detection.species.common_name(language)
            label_line = "\n".join(f"<b>{label}</b>" for label in labels)
            return (
                f"{label_line}\n\n"
                f"<b>{common}</b>\n"
                f"<i>{detection.species.scientific_name}</i>\n\n"
                f"{_('Confidence')}: {detection.confidence:.0%}"
            )
