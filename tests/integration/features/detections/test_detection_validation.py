from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.detections import queries as detection_queries
from backyardchirps.features.detections.entity import SpeciesAlreadyIdentifiedException
from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.features.species.entity import Species
from backyardchirps.models.stored_detection import StoredDetection

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"


def test_confirm_marks_human_confirmed(create_detection: Callable[..., Any]) -> None:
    detection = create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING, confidence=0.6)

    detection_queries.confirm(detection.id)

    updated = detection_queries.get_by_id(detection.id)
    assert updated.validation_status == ValidationStatus.HUMAN_CONFIRMED
    # The score stays as BirdNET reported it. The status is what says a person checked it.
    assert updated.confidence == 0.6


def test_confirm_with_reassignment(create_detection: Callable[..., Any]) -> None:
    detection = create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING)

    detection_queries.confirm(detection.id, reassigned_species=Species(ROBIN))

    updated = detection_queries.get_by_id(detection.id)
    assert updated.species == Species(ROBIN)
    assert updated.validation_status == ValidationStatus.HUMAN_CONFIRMED


def test_reassigning_to_a_species_the_recording_already_holds_is_refused(
    create_detection: Callable[..., Any], tmp_path: Path
) -> None:
    """
    Two birds in one recording, and the reassignment would turn them into two robins. The
    dialog cannot even ask for this, so refusing is better than guessing what was meant.
    Nothing changes either way.
    """
    recorded_at = datetime(2024, 6, 15, 8, 7, 31, tzinfo=timezone.utc)
    blackbird_clip = tmp_path / "blackbird.wav"
    blackbird_clip.write_bytes(b"audio")
    robin = create_detection(scientific_name=ROBIN, recorded_at=recorded_at, confidence=0.95)
    blackbird = create_detection(
        scientific_name=BLACKBIRD,
        recorded_at=recorded_at,
        confidence=0.79,
        validation_status=ValidationStatus.PENDING,
        clip_path=str(blackbird_clip),
    )

    with pytest.raises(SpeciesAlreadyIdentifiedException):
        detection_queries.confirm(blackbird.id, reassigned_species=Species(ROBIN))

    assert blackbird_clip.exists()  # nothing deleted
    reviewed = detection_queries.get_by_id(blackbird.id)
    assert reviewed.species == Species(BLACKBIRD)  # nor reassigned
    assert reviewed.validation_status == ValidationStatus.PENDING  # still queued
    assert detection_queries.get_by_id(robin.id).validation_status == ValidationStatus.AUTO_CONFIRMED


def test_reassigning_is_allowed_when_the_recording_differs(create_detection: Callable[..., Any]) -> None:
    """
    Same species, same batch window, different recordings: two genuine
    sightings, so the reassignment goes through and the other is untouched.
    """
    robin = create_detection(
        scientific_name=ROBIN,
        recorded_at=datetime(2024, 6, 15, 8, 6, 10, tzinfo=timezone.utc),
    )
    blackbird = create_detection(
        scientific_name=BLACKBIRD,
        recorded_at=datetime(2024, 6, 15, 8, 7, 31, tzinfo=timezone.utc),
        validation_status=ValidationStatus.PENDING,
    )

    detection_queries.confirm(blackbird.id, reassigned_species=Species(ROBIN))

    assert detection_queries.get_by_id(blackbird.id).species == Species(ROBIN)
    assert detection_queries.get_by_id(robin.id).validation_status == ValidationStatus.AUTO_CONFIRMED


def test_discard_deletes_clip_file_and_row(create_detection: Callable[..., Any], tmp_path: Path) -> None:
    clip_file = tmp_path / "clip.wav"
    clip_file.write_bytes(b"audio")
    detection = create_detection(scientific_name=BLACKBIRD, clip_path=str(clip_file))

    detection_queries.discard(detection.id)

    assert not clip_file.exists()  # clip removed from disk
    with pytest.raises(StoredDetection.DoesNotExist):
        detection_queries.get_by_id(detection.id)  # row removed
