from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.detections.entity import Detection
from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.features.notifications import logic as notifications
from backyardchirps.features.notifications.logic import FirstDetectionThisYearRule
from backyardchirps.features.notifications.logic import FirstDetectionTodayRule
from backyardchirps.features.notifications.logic import LongAbsentSpeciesRule
from backyardchirps.features.notifications.logic import NewSpeciesRule
from backyardchirps.features.notifications.logic import Notifier
from backyardchirps.features.notifications.logic import PendingValidationRule
from backyardchirps.features.notifications.logic import RareSpeciesRule
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.species.entity import Species
from backyardchirps.features.species.taxonomy import taxonomy

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"

_NOW = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)


def _detection(
    confidence: float = 0.95,
    recorded_at: datetime = _NOW,
    validation_status: ValidationStatus = ValidationStatus.AUTO_CONFIRMED,
) -> Detection:
    return Detection(
        id=1,
        species=Species(BLACKBIRD),
        recorded_at=recorded_at,
        confidence=confidence,
        clip_path=None,
        clip_duration_seconds=None,
        validation_status=validation_status,
    )


# --- NewSpeciesRule ----------------------------------------------------------


def test_new_species_fires_when_never_seen_before() -> None:
    assert NewSpeciesRule().should_notify(_detection()) is True


def test_new_species_silent_when_seen_before(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=_NOW - timedelta(days=1))
    assert NewSpeciesRule().should_notify(_detection()) is False


def test_new_species_silent_when_disabled() -> None:
    Settings.set(SettingsKey.NOTIFICATIONS_NEW_SPECIES_ENABLED, "false")
    assert NewSpeciesRule().should_notify(_detection()) is False


def test_new_species_silent_below_confidence() -> None:
    assert NewSpeciesRule().should_notify(_detection(confidence=0.5)) is False


# --- FirstDetectionTodayRule -------------------------------------------------


def test_first_today_fires_with_no_earlier_detection_today() -> None:
    assert FirstDetectionTodayRule().should_notify(_detection()) is True


def test_first_today_silent_after_earlier_detection_today(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=_NOW - timedelta(hours=1), confidence=0.95)
    assert FirstDetectionTodayRule().should_notify(_detection()) is False


# --- FirstDetectionThisYearRule ----------------------------------------------


def test_first_year_fires_with_no_earlier_detection_this_year() -> None:
    assert FirstDetectionThisYearRule().should_notify(_detection()) is True


def test_first_year_silent_after_earlier_detection_this_year(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 3, 1, tzinfo=timezone.utc), confidence=0.95)
    assert FirstDetectionThisYearRule().should_notify(_detection()) is False


# --- LongAbsentSpeciesRule ---------------------------------------------------


def test_long_absent_fires_after_a_gap(create_detection: Callable[..., Any]) -> None:
    # Seen 40 days ago (before the 30-day cutoff), nothing since.
    create_detection(scientific_name=BLACKBIRD, recorded_at=_NOW - timedelta(days=40), confidence=0.95)
    assert LongAbsentSpeciesRule().should_notify(_detection()) is True


def test_long_absent_silent_when_seen_recently(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=_NOW - timedelta(days=40), confidence=0.95)
    create_detection(scientific_name=BLACKBIRD, recorded_at=_NOW - timedelta(days=10), confidence=0.95)
    assert LongAbsentSpeciesRule().should_notify(_detection()) is False


# --- RareSpeciesRule ---------------------------------------------------------


def test_rare_fires_for_non_local_species(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(taxonomy, "_local_species", {"Passer domesticus"})  # blackbird not local -> rare
    assert RareSpeciesRule().should_notify(_detection(confidence=0.8)) is True


def test_rare_silent_for_local_species(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(taxonomy, "_local_species", {BLACKBIRD})  # blackbird local -> not rare
    assert RareSpeciesRule().should_notify(_detection(confidence=0.8)) is False


# --- PendingValidationRule ---------------------------------------------------


def test_pending_validation_fires_for_pending_detection() -> None:
    assert PendingValidationRule().should_notify(_detection(validation_status=ValidationStatus.PENDING)) is True


def test_pending_validation_silent_for_confirmed_detection() -> None:
    assert PendingValidationRule().should_notify(_detection(validation_status=ValidationStatus.AUTO_CONFIRMED)) is False


# --- Notifier._evaluate_and_send --------------------------------------------


class _SendRecorder:
    def __init__(self) -> None:
        self.captions: list[str] = []

    async def __call__(self, token: str, chat_id: str, photo: Any, caption: str, audio: Any) -> None:
        self.captions.append(caption)


@pytest.fixture
def send_recorder(monkeypatch: pytest.MonkeyPatch, settings: Any) -> _SendRecorder:
    settings.NOTIFICATIONS = {"telegram_token": "token", "telegram_chat_id": "chat"}
    # Avoid depending on which species have bundled image files.
    monkeypatch.setattr(Species, "image_path", property(lambda self: None))
    recorder = _SendRecorder()
    monkeypatch.setattr(notifications, "send_photo_and_audio", recorder)
    return recorder


def test_evaluate_and_send_dispatches_when_a_rule_matches(
    send_recorder: _SendRecorder, make_audio_clip: Callable[..., Any]
) -> None:
    notifier = Notifier()

    notifier._evaluate_and_send(_detection(validation_status=ValidationStatus.PENDING), make_audio_clip())

    assert len(send_recorder.captions) == 1
    assert BLACKBIRD in send_recorder.captions[0]  # scientific name is in the caption


def test_evaluate_and_send_skips_blacklisted(
    send_recorder: _SendRecorder, make_audio_clip: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    create_override(scientific_name=BLACKBIRD, blacklisted=True)
    notifier = Notifier()

    notifier._evaluate_and_send(_detection(validation_status=ValidationStatus.PENDING), make_audio_clip())

    assert send_recorder.captions == []


def test_evaluate_and_send_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch, settings: Any, make_audio_clip: Callable[..., Any]
) -> None:
    settings.NOTIFICATIONS = {"telegram_token": "", "telegram_chat_id": ""}
    recorder = _SendRecorder()
    monkeypatch.setattr(notifications, "send_photo_and_audio", recorder)

    Notifier()._evaluate_and_send(_detection(validation_status=ValidationStatus.PENDING), make_audio_clip())

    assert recorder.captions == []
