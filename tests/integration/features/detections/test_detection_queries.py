from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path
from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.detections import queries as detection_queries
from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import RawCandidate
from backyardchirps.features.species.entity import Species
from backyardchirps.models.stored_detection import StoredDetection

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"
HOUSE_SPARROW = "Passer domesticus"

_RECORDED_AT = datetime(2024, 6, 15, 8, 6, 0, tzinfo=timezone.utc)


def _clip(make_audio_clip: Callable[..., AudioClip], recorded_at: datetime = _RECORDED_AT) -> AudioClip:
    return make_audio_clip(seconds=3.0, recorded_at=recorded_at)


def _result(confidence: float, scientific_name: str = BLACKBIRD) -> AnalysisResult:
    return AnalysisResult(species=Species(scientific_name), confidence=confidence)


# --- upsert -----------------------------------------------------------------


def test_upsert_creates_detection_and_saves_clip(make_audio_clip: Callable[..., AudioClip], clips_dir: Path) -> None:
    detection = detection_queries.upsert(_clip(make_audio_clip), _result(0.8))

    assert detection is not None
    assert detection.confidence == 0.8
    # 0.8 is below the default auto-confirm bar, so it waits for review.
    assert detection.validation_status == ValidationStatus.PENDING
    assert detection.clip_path is not None
    assert Path(detection.clip_path).exists()
    assert Path(detection.clip_path).parent == clips_dir


def test_upsert_gives_every_species_in_one_clip_the_same_recorded_at(
    make_audio_clip: Callable[..., AudioClip], clips_dir: Path
) -> None:
    """
    Two species heard in one clip get a row and a clip file each, but share a
    recorded_at. That is what later lets a review tell they were the same audio.
    """
    clip = _clip(make_audio_clip)

    detection_queries.upsert(clip, _result(0.95, ROBIN))
    detection_queries.upsert(clip, _result(0.79, BLACKBIRD))

    assert set(StoredDetection.objects.values_list("recorded_at", flat=True)) == {_RECORDED_AT}


def test_upsert_moves_recorded_at_onto_the_replacing_clip(
    make_audio_clip: Callable[..., AudioClip], clips_dir: Path
) -> None:
    """
    A better-confidence hit swaps in its own clip, so recorded_at has to follow
    it rather than keep pointing at the audio that was just deleted.
    """
    replacement_recorded_at = _RECORDED_AT + timedelta(seconds=45)
    detection_queries.upsert(_clip(make_audio_clip), _result(0.6))

    detection_queries.upsert(_clip(make_audio_clip, replacement_recorded_at), _result(0.85))

    assert StoredDetection.objects.get().recorded_at == replacement_recorded_at


def test_upsert_replaces_lower_confidence_in_same_block(
    make_audio_clip: Callable[..., AudioClip], clips_dir: Path
) -> None:
    first = detection_queries.upsert(_clip(make_audio_clip), _result(0.6))
    assert first is not None
    assert first.clip_path is not None
    old_clip_path = first.clip_path

    second = detection_queries.upsert(_clip(make_audio_clip), _result(0.85))

    assert second is not None
    assert second.clip_path is not None
    assert second.confidence == 0.85
    assert not Path(old_clip_path).exists()  # old clip deleted
    assert Path(second.clip_path).exists()


def test_upsert_ignores_equal_or_lower_confidence(make_audio_clip: Callable[..., AudioClip], clips_dir: Path) -> None:
    first = detection_queries.upsert(_clip(make_audio_clip), _result(0.8))
    assert first is not None
    assert first.clip_path is not None

    assert detection_queries.upsert(_clip(make_audio_clip), _result(0.8)) is None  # equal
    assert detection_queries.upsert(_clip(make_audio_clip), _result(0.7)) is None  # lower
    assert Path(first.clip_path).exists()  # original clip untouched


def test_upsert_marks_low_confidence_as_pending(make_audio_clip: Callable[..., AudioClip], clips_dir: Path) -> None:
    # Default global auto-confirm bar is ANALYSIS_AUTO_CONFIRM_CONFIDENCE = 0.9.
    detection = detection_queries.upsert(_clip(make_audio_clip), _result(0.6))
    assert detection is not None
    assert detection.validation_status == ValidationStatus.PENDING


def test_upsert_uses_per_species_override_threshold(
    make_audio_clip: Callable[..., AudioClip], clips_dir: Path, create_override: Callable[..., Any]
) -> None:
    # A custom threshold of 0.5 auto-confirms a 0.6 detection that the global 0.9 bar would pend.
    create_override(scientific_name=BLACKBIRD, threshold=0.5)

    detection = detection_queries.upsert(_clip(make_audio_clip), _result(0.6))

    assert detection is not None
    assert detection.validation_status == ValidationStatus.AUTO_CONFIRMED


def test_upsert_keeps_the_analysis_time_and_the_raw_candidates(
    make_audio_clip: Callable[..., AudioClip], clips_dir: Path
) -> None:
    detection = detection_queries.upsert(
        _clip(make_audio_clip),
        _result(0.8),
        analysis_time_ms=175,
        raw_candidates=[RawCandidate(label=BLACKBIRD, confidence=0.8), RawCandidate(label="Engine", confidence=0.2)],
    )

    assert detection is not None
    assert detection.analysis_time_ms == 175
    # The raw list keeps the non-bird token and its confidence, unresolved to a species.
    assert [(candidate.label, candidate.species) for candidate in detection.analysis_candidates] == [
        (BLACKBIRD, Species(BLACKBIRD)),
        ("Engine", None),
    ]


# --- species_with_detection_counts ------------------------------------------


def test_species_with_detection_counts_totals_and_ordering(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=_RECORDED_AT)
    create_detection(scientific_name=BLACKBIRD, recorded_at=_RECORDED_AT + timedelta(hours=1))
    create_detection(scientific_name=ROBIN, recorded_at=_RECORDED_AT + timedelta(hours=2))

    by_frequency = detection_queries.species_with_detection_counts(order="most_frequent")
    assert [row.species.scientific_name for row in by_frequency] == [BLACKBIRD, ROBIN]
    assert by_frequency[0].count_total == 2

    by_recent = detection_queries.species_with_detection_counts(order="most_recent")
    assert by_recent[0].species.scientific_name == ROBIN  # most recent detection


def test_species_with_detection_counts_excludes_blacklisted(
    create_detection: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    create_detection(scientific_name=BLACKBIRD)
    create_detection(scientific_name=ROBIN)
    create_override(scientific_name=ROBIN, blacklisted=True)

    names = [row.species.scientific_name for row in detection_queries.species_with_detection_counts()]

    assert BLACKBIRD in names
    assert ROBIN not in names


def test_species_with_detection_counts_leaves_out_the_review_queue(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.AUTO_CONFIRMED)
    create_detection(scientific_name=ROBIN, validation_status=ValidationStatus.PENDING)

    counts = detection_queries.species_with_detection_counts()

    assert [row.species.scientific_name for row in counts] == [BLACKBIRD]


def test_species_with_detection_counts_counts_only_approved_rows(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.AUTO_CONFIRMED)
    create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.HUMAN_CONFIRMED)
    create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING)

    counts = detection_queries.species_with_detection_counts()

    assert [row.count_total for row in counts] == [2]


# --- dubious / validation ----------------------------------------------------


def test_dubious_detections_returns_pending_excluding_blacklisted(
    create_detection: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING)
    create_detection(scientific_name=ROBIN, validation_status=ValidationStatus.PENDING)
    create_detection(scientific_name=HOUSE_SPARROW, validation_status=ValidationStatus.AUTO_CONFIRMED)
    create_override(scientific_name=ROBIN, blacklisted=True)

    dubious = detection_queries.get_dubious_detections()
    names = [detection.species.scientific_name for detection in dubious]

    assert names == [BLACKBIRD]  # robin blacklisted, sparrow confirmed
    assert detection_queries.count_dubious_detections() == 1


def test_confirm_reassigns_species(create_detection: Callable[..., Any]) -> None:
    detection = create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING)

    detection_queries.confirm(
        detection.id,
        reassigned_species=Species(ROBIN),
    )

    updated = detection_queries.get_by_id(detection.id)
    assert updated.species.scientific_name == ROBIN
    assert updated.confidence == 1.0
    assert updated.validation_status == ValidationStatus.HUMAN_CONFIRMED


def test_confirm_snapshots_the_original_birdnet_identification(
    create_detection: Callable[..., Any],
) -> None:
    detection = create_detection(scientific_name=BLACKBIRD, confidence=0.6, validation_status=ValidationStatus.PENDING)

    detection_queries.confirm(
        detection.id,
        reassigned_species=Species(ROBIN),
    )

    stored = StoredDetection.objects.get(pk=detection.id)
    assert stored.original_species.scientific_name == BLACKBIRD
    assert stored.original_confidence == 0.6


def test_confirm_keeps_the_first_snapshot_when_revalidated(
    create_detection: Callable[..., Any],
) -> None:
    detection = create_detection(scientific_name=BLACKBIRD, confidence=0.6, validation_status=ValidationStatus.PENDING)

    detection_queries.confirm(
        detection.id,
        reassigned_species=Species(ROBIN),
    )
    detection_queries.confirm(
        detection.id,
        reassigned_species=Species(HOUSE_SPARROW),
    )

    stored = StoredDetection.objects.get(pk=detection.id)
    # Still BirdNET's identification, not the robin the first reviewer chose.
    assert stored.original_species.scientific_name == BLACKBIRD
    assert stored.original_confidence == 0.6


def test_confirm_snapshots_original_even_without_reassignment(
    create_detection: Callable[..., Any],
) -> None:
    detection = create_detection(scientific_name=BLACKBIRD, confidence=0.6, validation_status=ValidationStatus.PENDING)

    detection_queries.confirm(detection.id)

    stored = StoredDetection.objects.get(pk=detection.id)
    assert stored.original_species.scientific_name == BLACKBIRD
    assert stored.original_confidence == 0.6


def test_auto_confirm_pending_above_flips_only_qualifying_rows(create_detection: Callable[..., Any]) -> None:
    below = create_detection(scientific_name=BLACKBIRD, confidence=0.4, validation_status=ValidationStatus.PENDING)
    above = create_detection(scientific_name=BLACKBIRD, confidence=0.8, validation_status=ValidationStatus.PENDING)

    reclassified = detection_queries.auto_confirm_pending_above(Species(BLACKBIRD), threshold=0.5)

    assert reclassified == 1
    assert detection_queries.get_by_id(above.id).validation_status == ValidationStatus.AUTO_CONFIRMED
    assert detection_queries.get_by_id(below.id).validation_status == ValidationStatus.PENDING
    # Confidence is preserved, not overwritten to 1.0.
    assert detection_queries.get_by_id(above.id).confidence == 0.8


# --- history predicates ------------------------------------------------------


def test_has_detection_before(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=_RECORDED_AT)
    species = Species(BLACKBIRD)

    assert detection_queries.has_detection_before(species, _RECORDED_AT + timedelta(seconds=1)) is True
    assert detection_queries.has_detection_before(species, _RECORDED_AT) is False  # strictly before


def test_has_detection_in_range_respects_bounds_and_confidence(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=_RECORDED_AT, confidence=0.9)
    species = Species(BLACKBIRD)
    hour_after = _RECORDED_AT + timedelta(hours=1)

    assert detection_queries.has_detection_in_range(species, _RECORDED_AT, hour_after, min_confidence=0.8) is True
    # Confidence filter excludes it.
    assert detection_queries.has_detection_in_range(species, _RECORDED_AT, hour_after, min_confidence=0.95) is False
    # before_dt is exclusive: a window ending exactly at the detection excludes it.
    hour_before = _RECORDED_AT - timedelta(hours=1)
    assert detection_queries.has_detection_in_range(species, hour_before, _RECORDED_AT, min_confidence=0.0) is False
