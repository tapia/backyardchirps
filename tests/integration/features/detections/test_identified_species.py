"""
What the review dialog is told about the rest of a recording: the other species
it was identified as, which is what stops a reviewer identifying one bird twice.
"""

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.detections import queries as detection_repository
from backyardchirps.features.species.entity import Species

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"
HOUSE_SPARROW = "Passer domesticus"

RECORDING = datetime(2024, 6, 15, 8, 7, 31, tzinfo=timezone.utc)
ANOTHER_RECORDING = datetime(2024, 6, 15, 8, 6, 10, tzinfo=timezone.utc)


def test_lists_the_other_species_in_the_same_recording(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=ROBIN, recorded_at=RECORDING)
    create_detection(scientific_name=HOUSE_SPARROW, recorded_at=RECORDING)
    blackbird = create_detection(scientific_name=BLACKBIRD, recorded_at=RECORDING)

    identified = detection_repository.species_identified_in_same_recording(blackbird.to_entity())

    assert set(identified) == {Species(ROBIN), Species(HOUSE_SPARROW)}


def test_a_recording_with_one_bird_lists_nothing(create_detection: Callable[..., Any]) -> None:
    """
    The ordinary case. Its own species is never listed back to it, so a single
    identification leaves the dialog in its plain single-species layout.
    """
    blackbird = create_detection(scientific_name=BLACKBIRD, recorded_at=RECORDING)

    identified = detection_repository.species_identified_in_same_recording(blackbird.to_entity())

    assert identified == []


def test_a_different_recording_is_not_listed(create_detection: Callable[..., Any]) -> None:
    """
    Same species, same batch window, different audio. Those are two separate
    sightings, and reassigning onto one of them stays allowed.
    """
    create_detection(scientific_name=ROBIN, recorded_at=ANOTHER_RECORDING)
    blackbird = create_detection(scientific_name=BLACKBIRD, recorded_at=RECORDING)

    identified = detection_repository.species_identified_in_same_recording(blackbird.to_entity())

    assert identified == []


def test_blacklisted_species_are_left_out(
    create_detection: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    create_override(scientific_name=ROBIN, blacklisted=True)
    create_detection(scientific_name=ROBIN, recorded_at=RECORDING)
    blackbird = create_detection(scientific_name=BLACKBIRD, recorded_at=RECORDING)

    identified = detection_repository.species_identified_in_same_recording(blackbird.to_entity())

    assert identified == []


def test_capture_times_a_fraction_apart_are_different_recordings(create_detection: Callable[..., Any]) -> None:
    """
    Two rows one microsecond apart are not from the same clip.

    This matters for rows that lost their exact capture time along with their clip. Each
    was given the start of its block plus a microsecond of its own, which puts it in the
    right hour while keeping it apart from the others. That only holds while a difference
    this small is enough to separate them.
    """
    create_detection(scientific_name=ROBIN, recorded_at=RECORDING)
    blackbird = create_detection(scientific_name=BLACKBIRD, recorded_at=RECORDING + timedelta(microseconds=1))

    identified = detection_repository.species_identified_in_same_recording(blackbird.to_entity())

    assert identified == []
