from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.logic import discard_blacklisted
from backyardchirps.features.species.entity import Species

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"


def test_discard_blacklisted_drops_only_blacklisted_species(create_override: Callable[..., Any]) -> None:
    create_override(scientific_name=ROBIN, blacklisted=True)
    results = [
        AnalysisResult(species=Species(BLACKBIRD), confidence=0.8),
        AnalysisResult(species=Species(ROBIN), confidence=0.9),
    ]

    kept = discard_blacklisted(results)

    assert [result.species.scientific_name for result in kept] == [BLACKBIRD]


def test_discard_blacklisted_keeps_everything_when_nothing_is_blacklisted() -> None:
    results = [
        AnalysisResult(species=Species(BLACKBIRD), confidence=0.8),
        AnalysisResult(species=Species(ROBIN), confidence=0.9),
    ]

    kept = discard_blacklisted(results)

    assert [result.species.scientific_name for result in kept] == [BLACKBIRD, ROBIN]
