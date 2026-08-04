from typing import Callable

import pytest

from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.consistency_filter import ConsistencyFilter
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import RawCandidate
from backyardchirps.features.species.entity import Species

# Test clips are 3 s at 48 kHz with a 1.5 s overlap, matching the production config.
_SAMPLE_RATE = 48000
_CLIP_SECONDS = 3.0
_OVERLAP_TIME = 1.5

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"


@pytest.fixture
def clip(make_audio_clip: Callable[..., AudioClip]) -> AudioClip:
    return make_audio_clip(seconds=_CLIP_SECONDS, sample_rate=_SAMPLE_RATE)


def _result(scientific_name: str, confidence: float) -> AnalysisResult:
    return AnalysisResult(species=Species(scientific_name), confidence=confidence)


def _filter(window_size: int, min_detections: int, bypass_confidence: float) -> ConsistencyFilter:
    return ConsistencyFilter(
        window_size=window_size,
        min_detections=min_detections,
        bypass_confidence=bypass_confidence,
        overlap_time=_OVERLAP_TIME,
    )


def test_repetition_confirms_at_threshold_and_merges_window(clip: AudioClip) -> None:
    consistency_filter = _filter(window_size=3, min_detections=2, bypass_confidence=0.99)

    assert consistency_filter.add(clip, [_result(BLACKBIRD, 0.60)]) == []

    confirmed = consistency_filter.add(clip, [_result(BLACKBIRD, 0.65)])
    assert len(confirmed) == 1
    assert confirmed[0].result.species.scientific_name == BLACKBIRD
    # Confidence is the maximum seen across the window.
    assert confirmed[0].result.confidence == 0.65
    # Two 3 s clips sharing a 1.5 s overlap give 3 + (3 - 1.5) = 4.5 s.
    assert confirmed[0].clip.duration_seconds() == 4.5


def test_below_threshold_is_not_confirmed(clip: AudioClip) -> None:
    consistency_filter = _filter(window_size=3, min_detections=3, bypass_confidence=0.99)

    assert consistency_filter.add(clip, [_result(BLACKBIRD, 0.60)]) == []
    assert consistency_filter.add(clip, [_result(BLACKBIRD, 0.60)]) == []


def test_bypass_confirms_single_clip_without_merging(clip: AudioClip) -> None:
    consistency_filter = _filter(window_size=3, min_detections=5, bypass_confidence=0.80)

    confirmed = consistency_filter.add(clip, [_result(BLACKBIRD, 0.85)])
    assert len(confirmed) == 1
    assert confirmed[0].result.confidence == 0.85
    # Bypass uses only the triggering clip, so no merge: it stays 3 s.
    assert confirmed[0].clip.duration_seconds() == 3.0


def test_window_eviction_prevents_confirmation(clip: AudioClip) -> None:
    # With window_size=2 the first clip is gone before the third arrives, so a species
    # heard only in clips 1 and 3 is never in the window twice at once.
    consistency_filter = _filter(window_size=2, min_detections=2, bypass_confidence=0.99)

    assert consistency_filter.add(clip, [_result(BLACKBIRD, 0.60)]) == []
    assert consistency_filter.add(clip, []) == []
    assert consistency_filter.add(clip, [_result(BLACKBIRD, 0.60)]) == []


def test_species_are_resolved_independently(clip: AudioClip) -> None:
    consistency_filter = _filter(window_size=3, min_detections=2, bypass_confidence=0.99)

    consistency_filter.add(clip, [_result(BLACKBIRD, 0.60), _result(ROBIN, 0.50)])
    confirmed = consistency_filter.add(clip, [_result(BLACKBIRD, 0.70)])

    # Only the blackbird reached two appearances; the robin has one and is not confirmed.
    assert len(confirmed) == 1
    assert confirmed[0].result.species.scientific_name == BLACKBIRD
    assert confirmed[0].result.confidence == 0.70


def test_confirmed_detection_carries_metadata_from_highest_confidence_clip(clip: AudioClip) -> None:
    consistency_filter = _filter(window_size=3, min_detections=2, bypass_confidence=0.99)

    consistency_filter.add(
        clip,
        [_result(BLACKBIRD, 0.60)],
        raw_candidates=[RawCandidate(label=BLACKBIRD, confidence=0.60)],
        analysis_time_ms=120,
    )
    confirmed = consistency_filter.add(
        clip,
        [_result(BLACKBIRD, 0.70)],
        raw_candidates=[RawCandidate(label=BLACKBIRD, confidence=0.70), RawCandidate(label="Engine", confidence=0.30)],
        analysis_time_ms=140,
    )

    # The metadata comes from the second clip, where the blackbird scored highest.
    assert confirmed[0].analysis_time_ms == 140
    assert [candidate.label for candidate in confirmed[0].raw_candidates] == [BLACKBIRD, "Engine"]
