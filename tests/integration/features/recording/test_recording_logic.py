from pathlib import Path
from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.recording import logic as process_recording
from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.consistency_filter import ConfirmedDetection
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import RawCandidate
from backyardchirps.features.species.entity import Species

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"
CRICKET = "Acheta domesticus"  # an insect in BirdNET's taxonomy


def test_discard_blacklisted_drops_only_blacklisted_species(create_override: Callable[..., Any]) -> None:
    create_override(scientific_name=ROBIN, blacklisted=True)
    results = [
        AnalysisResult(species=Species(BLACKBIRD), confidence=0.8),
        AnalysisResult(species=Species(ROBIN), confidence=0.9),
    ]

    kept = process_recording.discard_blacklisted(results)

    assert [result.species.scientific_name for result in kept] == [BLACKBIRD]


def test_discard_non_birds_drops_non_bird_taxa() -> None:
    results = [
        AnalysisResult(species=Species(BLACKBIRD), confidence=0.8),
        AnalysisResult(species=Species(CRICKET), confidence=0.9),
    ]

    kept = process_recording.discard_non_birds(results)

    assert [result.species.scientific_name for result in kept] == [BLACKBIRD]


def test_process_confirmed_detection_persists(
    make_audio_clip: Callable[..., AudioClip], make_result: Callable[..., AnalysisResult], clips_dir: Path
) -> None:
    confirmed = ConfirmedDetection(
        clip=make_audio_clip(seconds=3.0),
        result=make_result(BLACKBIRD, 0.8),
        analysis_time_ms=175,
        raw_candidates=[RawCandidate(label=BLACKBIRD, confidence=0.8), RawCandidate(label="Engine", confidence=0.2)],
    )

    detection = process_recording.process_confirmed_detection(confirmed)

    assert detection is not None
    assert detection.species == Species(BLACKBIRD)
    assert detection.clip_path is not None
    assert Path(detection.clip_path).exists()
    assert detection.analysis_time_ms == 175
    # The raw list keeps the non-bird token and its confidence, unresolved to a species.
    assert [(candidate.label, candidate.species) for candidate in detection.analysis_candidates] == [
        (BLACKBIRD, Species(BLACKBIRD)),
        ("Engine", None),
    ]
