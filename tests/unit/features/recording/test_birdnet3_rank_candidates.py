import numpy as np

from backyardchirps.features.recording.audio.birdnet3.analyzer import rank_candidates
from backyardchirps.features.recording.audio.detection import RAW_CANDIDATE_FLOOR
from backyardchirps.features.species.entity import Species

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"
CRICKET = "Acheta domesticus"  # an insect: a label with no bird species, kept raw

_DETECTION_FLOOR = 0.4


def _scores(values: dict[int, float], size: int = 6) -> np.ndarray:
    scores = np.zeros(size, dtype=np.float32)
    for index, value in values.items():
        scores[index] = value
    return scores


def test_raw_list_keeps_candidates_below_the_detection_floor() -> None:
    # Three classes: one clears the detection floor, two sit between the raw
    # floor and the detection floor.
    per_class_best = _scores({0: 0.85, 1: 0.30, 2: 0.08})
    labels = {0: BLACKBIRD, 1: ROBIN, 2: CRICKET}
    species_by_index = {0: Species(BLACKBIRD), 1: Species(ROBIN)}

    analysis = rank_candidates(
        per_class_best=per_class_best,
        labels=[labels.get(index, f"label-{index}") for index in range(len(per_class_best))],
        species_by_index=species_by_index,
        allowed_species=None,
        min_confidence=_DETECTION_FLOOR,
    )

    # Only the class above the detection floor becomes a result.
    assert [result.species.scientific_name for result in analysis.results] == [BLACKBIRD]
    # The raw list goes all the way down to the raw floor, highest first, and keeps both
    # the bird below the detection floor and the insect label.
    assert [(candidate.label, round(candidate.confidence, 2)) for candidate in analysis.raw_candidates] == [
        (BLACKBIRD, 0.85),
        (ROBIN, 0.30),
        (CRICKET, 0.08),
    ]


def test_scores_below_the_raw_floor_are_dropped() -> None:
    per_class_best = _scores({0: 0.9, 1: RAW_CANDIDATE_FLOOR - 0.01})
    analysis = rank_candidates(
        per_class_best=per_class_best,
        labels=[BLACKBIRD, ROBIN, "l2", "l3", "l4", "l5"],
        species_by_index={0: Species(BLACKBIRD), 1: Species(ROBIN)},
        allowed_species=None,
        min_confidence=_DETECTION_FLOOR,
    )

    assert [candidate.label for candidate in analysis.raw_candidates] == [BLACKBIRD]


def test_location_filter_drops_known_species_out_of_range() -> None:
    per_class_best = _scores({0: 0.9, 1: 0.5})
    analysis = rank_candidates(
        per_class_best=per_class_best,
        labels=[BLACKBIRD, ROBIN, "l2", "l3", "l4", "l5"],
        species_by_index={0: Species(BLACKBIRD), 1: Species(ROBIN)},
        allowed_species={Species(BLACKBIRD)},
        min_confidence=_DETECTION_FLOOR,
    )

    # The robin is out of range, so it leaves both lists.
    assert [candidate.label for candidate in analysis.raw_candidates] == [BLACKBIRD]
    assert [result.species.scientific_name for result in analysis.results] == [BLACKBIRD]
