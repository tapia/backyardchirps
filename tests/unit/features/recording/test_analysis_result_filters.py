from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import discard_non_birds
from backyardchirps.features.species.entity import Species

BLACKBIRD = "Turdus merula"
CRICKET = "Acheta domesticus"  # an insect in BirdNET's taxonomy


def test_discard_non_birds_drops_non_bird_taxa() -> None:
    results = [
        AnalysisResult(species=Species(BLACKBIRD), confidence=0.8),
        AnalysisResult(species=Species(CRICKET), confidence=0.9),
    ]

    kept = discard_non_birds(results)

    assert [result.species.scientific_name for result in kept] == [BLACKBIRD]


def test_discard_non_birds_keeps_an_empty_list_empty() -> None:
    assert discard_non_birds([]) == []
