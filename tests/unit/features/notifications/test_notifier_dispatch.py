from datetime import datetime
from datetime import timezone
from typing import Callable

import pytest

from backyardchirps.features.detections.entity import Detection
from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.features.notifications.logic import Notifier
from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.species.entity import Species

BLACKBIRD = "Turdus merula"

_T0 = datetime(2024, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
_T1 = datetime(2024, 6, 15, 8, 3, 0, tzinfo=timezone.utc)


def _detection(detection_id: int, recorded_at: datetime, confidence: float = 0.9) -> Detection:
    return Detection(
        id=detection_id,
        species=Species(BLACKBIRD),
        recorded_at=recorded_at,
        confidence=confidence,
        clip_path=None,
        clip_duration_seconds=None,
        validation_status=ValidationStatus.AUTO_CONFIRMED,
    )


def test_flush_only_evaluates_detections_whose_block_has_closed(
    monkeypatch: pytest.MonkeyPatch, make_audio_clip: Callable[..., AudioClip]
) -> None:
    notifier = Notifier()
    evaluated: list[int] = []
    monkeypatch.setattr(notifier, "_evaluate_and_send", lambda detection, clip: evaluated.append(detection.id))

    clip = make_audio_clip()
    notifier.maybe_notify(_detection(1, _T0), clip)
    notifier.maybe_notify(_detection(2, _T1), clip)

    # Block time sits between the two: only detection 1 has closed.
    notifier.flush(datetime(2024, 6, 15, 8, 1, 0, tzinfo=timezone.utc))
    assert evaluated == [1]

    # Later block closes detection 2; detection 1 is not re-sent.
    notifier.flush(datetime(2024, 6, 15, 8, 6, 0, tzinfo=timezone.utc))
    assert evaluated == [1, 2]


def test_build_caption_contains_names_labels_and_confidence() -> None:
    caption = Notifier()._build_caption(_detection(1, _T0, confidence=0.9), ["First detection today"], "en")

    assert "First detection today" in caption
    assert "Common Blackbird" in caption
    assert BLACKBIRD in caption
    assert "90%" in caption
