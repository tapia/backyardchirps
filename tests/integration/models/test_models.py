from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.features.species.entity import Species
from backyardchirps.models.detected_species import DetectedSpecies
from backyardchirps.models.stored_detection import StoredDetection

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"

_AT = datetime(2024, 6, 15, 8, 6, 0, tzinfo=timezone.utc)


def test_of_species_filters_by_scientific_name(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD)
    create_detection(scientific_name=ROBIN)

    queryset = StoredDetection.objects.of_species(Species(BLACKBIRD))

    assert queryset.count() == 1
    assert queryset.first().species.scientific_name == BLACKBIRD


def test_in_period_treats_none_as_unrestricted(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=_AT)
    create_detection(scientific_name=BLACKBIRD, recorded_at=_AT + timedelta(days=2))

    assert StoredDetection.objects.in_period(None, None).count() == 2
    assert StoredDetection.objects.in_period(_AT + timedelta(days=1), None).count() == 1


def test_approved_leaves_out_the_review_queue(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.AUTO_CONFIRMED)
    create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.HUMAN_CONFIRMED)
    create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING)

    assert StoredDetection.objects.approved().count() == 2


def test_with_min_confidence_passthrough_and_filter(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, confidence=0.4)
    create_detection(scientific_name=BLACKBIRD, confidence=0.9)

    assert StoredDetection.objects.with_min_confidence(None).count() == 2  # None = no restriction
    assert StoredDetection.objects.with_min_confidence(0.8).count() == 1


def test_excluding_blacklisted(create_detection: Callable[..., Any], create_override: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD)
    create_detection(scientific_name=ROBIN)
    create_override(scientific_name=ROBIN, blacklisted=True)

    names = {row.species.scientific_name for row in StoredDetection.objects.excluding_blacklisted()}

    assert names == {BLACKBIRD}


def test_with_saved_clip(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, clip_path="/clips/a.wav")
    create_detection(scientific_name=BLACKBIRD, clip_path=None)
    create_detection(scientific_name=BLACKBIRD, clip_path="")

    assert StoredDetection.objects.with_saved_clip().count() == 1


def test_to_entity_maps_row_to_entity(create_detection: Callable[..., Any]) -> None:
    row = create_detection(scientific_name=BLACKBIRD, recorded_at=_AT, confidence=0.8)

    detection = row.to_entity()

    assert detection is not None
    assert detection.species == Species(BLACKBIRD)
    assert detection.recorded_at == _AT
    assert detection.confidence == 0.8


def test_to_entity_returns_none_for_species_missing_from_taxonomy() -> None:
    # A taxonomy refresh can drop a name that old rows still carry.
    orphan_species = DetectedSpecies.objects.create(scientific_name="Gone extinctus")
    row = StoredDetection.objects.create(
        species=orphan_species,
        recorded_at=_AT,
        confidence=0.8,
    )

    assert row.to_entity() is None
