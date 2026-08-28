from typing import Callable

import pytest

from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import RawCandidate
from backyardchirps.features.recording.audio.detection_window import DetectionWindow
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


def _window(window_size: int, min_clips_to_merge: int) -> DetectionWindow:
    return DetectionWindow(
        window_size=window_size,
        min_clips_to_merge=min_clips_to_merge,
        overlap_time=_OVERLAP_TIME,
    )


def test_a_single_hearing_keeps_its_own_clip(clip: AudioClip) -> None:
    window = _window(window_size=3, min_clips_to_merge=2)

    recorded = window.add(clip, [_result(BLACKBIRD, 0.85)])

    assert len(recorded) == 1
    assert recorded[0].result.species.scientific_name == BLACKBIRD
    assert recorded[0].result.confidence == 0.85
    assert recorded[0].clip.duration_seconds() == _CLIP_SECONDS


def test_hearing_it_again_merges_the_window(clip: AudioClip) -> None:
    window = _window(window_size=3, min_clips_to_merge=2)

    window.add(clip, [_result(BLACKBIRD, 0.60)])
    recorded = window.add(clip, [_result(BLACKBIRD, 0.65)])

    assert len(recorded) == 1
    # Confidence is the maximum seen across the window.
    assert recorded[0].result.confidence == 0.65
    # Two 3 s clips sharing a 1.5 s overlap give 3 + (3 - 1.5) = 4.5 s.
    assert recorded[0].clip.duration_seconds() == 4.5


def test_the_recording_grows_while_the_bird_keeps_calling(clip: AudioClip) -> None:
    window = _window(window_size=3, min_clips_to_merge=2)

    durations = [
        window.add(clip, [_result(BLACKBIRD, 0.60)])[0].clip.duration_seconds(),
        window.add(clip, [_result(BLACKBIRD, 0.60)])[0].clip.duration_seconds(),
        window.add(clip, [_result(BLACKBIRD, 0.60)])[0].clip.duration_seconds(),
        # The window holds three clips, so the fourth one evicts the first.
        window.add(clip, [_result(BLACKBIRD, 0.60)])[0].clip.duration_seconds(),
    ]

    assert durations == [3.0, 4.5, 6.0, 6.0]


def test_a_clip_the_species_is_absent_from_reports_nothing(clip: AudioClip) -> None:
    window = _window(window_size=3, min_clips_to_merge=2)

    window.add(clip, [_result(BLACKBIRD, 0.85)])

    assert window.add(clip, []) == []


def test_a_gap_in_the_window_still_merges(clip: AudioClip) -> None:
    window = _window(window_size=3, min_clips_to_merge=2)

    window.add(clip, [_result(BLACKBIRD, 0.60)])
    window.add(clip, [])
    recorded = window.add(clip, [_result(BLACKBIRD, 0.70)])

    # Heard in two of the three clips still in the window, so the whole window is joined.
    assert recorded[0].clip.duration_seconds() == 6.0
    assert recorded[0].result.confidence == 0.70


def test_a_hearing_that_left_the_window_no_longer_merges(clip: AudioClip) -> None:
    # With window_size=2 the first clip is gone before the third arrives, so a species
    # heard only in clips 1 and 3 is never in the window twice at once.
    window = _window(window_size=2, min_clips_to_merge=2)

    window.add(clip, [_result(BLACKBIRD, 0.60)])
    window.add(clip, [])
    recorded = window.add(clip, [_result(BLACKBIRD, 0.60)])

    assert recorded[0].clip.duration_seconds() == _CLIP_SECONDS


def test_species_are_resolved_independently(clip: AudioClip) -> None:
    window = _window(window_size=3, min_clips_to_merge=2)

    window.add(clip, [_result(BLACKBIRD, 0.60), _result(ROBIN, 0.50)])
    recorded = window.add(clip, [_result(BLACKBIRD, 0.70)])

    # Only the blackbird is in the newest clip, and only it has reached two hearings.
    assert len(recorded) == 1
    assert recorded[0].result.species.scientific_name == BLACKBIRD
    assert recorded[0].result.confidence == 0.70
    assert recorded[0].clip.duration_seconds() == 4.5


def test_metadata_comes_from_the_highest_confidence_clip(clip: AudioClip) -> None:
    window = _window(window_size=3, min_clips_to_merge=2)

    window.add(
        clip,
        [_result(BLACKBIRD, 0.60)],
        raw_candidates=[RawCandidate(label=BLACKBIRD, confidence=0.60)],
        analysis_time_ms=120,
    )
    recorded = window.add(
        clip,
        [_result(BLACKBIRD, 0.70)],
        raw_candidates=[RawCandidate(label=BLACKBIRD, confidence=0.70), RawCandidate(label="Engine", confidence=0.30)],
        analysis_time_ms=140,
    )

    # The metadata comes from the second clip, where the blackbird scored highest.
    assert recorded[0].analysis_time_ms == 140
    assert [candidate.label for candidate in recorded[0].raw_candidates] == [BLACKBIRD, "Engine"]


def test_merging_can_be_turned_off(clip: AudioClip) -> None:
    window = _window(window_size=3, min_clips_to_merge=4)

    window.add(clip, [_result(BLACKBIRD, 0.60)])
    window.add(clip, [_result(BLACKBIRD, 0.60)])
    recorded = window.add(clip, [_result(BLACKBIRD, 0.60)])

    assert recorded[0].clip.duration_seconds() == _CLIP_SECONDS
