from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.detections import queries as detection_queries
from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.features.overrides import logic as species_overrides
from backyardchirps.features.overrides import queries as override_queries
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.species.entity import Species

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"

# The default global auto-confirm bar is ANALYSIS_AUTO_CONFIRM_CONFIDENCE = 0.9.


def _status(detection_id: int) -> ValidationStatus:
    return detection_queries.get_by_id(detection_id).validation_status


def test_set_override_with_no_customization_clears_it(
    create_detected_species: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    create_detected_species(BLACKBIRD)
    create_override(scientific_name=BLACKBIRD, threshold=0.5)

    result = species_overrides.set_override(Species(BLACKBIRD), auto_confirm_threshold=None, blacklisted=False)

    assert result is None
    assert override_queries.get(Species(BLACKBIRD)) is None


def test_lowering_the_bar_clears_the_pending_queue(
    create_detected_species: Callable[..., Any], create_detection: Callable[..., Any]
) -> None:
    create_detected_species(BLACKBIRD)
    low = create_detection(scientific_name=BLACKBIRD, confidence=0.6, validation_status=ValidationStatus.PENDING)
    high = create_detection(scientific_name=BLACKBIRD, confidence=0.8, validation_status=ValidationStatus.PENDING)

    # New bar 0.5 < global 0.7, so pending rows at/above 0.5 get auto-confirmed.
    species_overrides.set_override(Species(BLACKBIRD), auto_confirm_threshold=0.5, blacklisted=False)

    assert _status(low.id) == ValidationStatus.AUTO_CONFIRMED
    assert _status(high.id) == ValidationStatus.AUTO_CONFIRMED


def test_raising_the_bar_leaves_the_queue_untouched(
    create_detected_species: Callable[..., Any], create_detection: Callable[..., Any]
) -> None:
    create_detected_species(BLACKBIRD)
    pending = create_detection(scientific_name=BLACKBIRD, confidence=0.95, validation_status=ValidationStatus.PENDING)

    # New bar 0.98 > global 0.9: not lowered, so nothing is auto-confirmed.
    species_overrides.set_override(Species(BLACKBIRD), auto_confirm_threshold=0.98, blacklisted=False)

    assert _status(pending.id) == ValidationStatus.PENDING


def test_clear_override_reverts_to_global_and_clears_queue_if_lowered(
    create_detected_species: Callable[..., Any], create_detection: Callable[..., Any]
) -> None:
    create_detected_species(BLACKBIRD)
    # Start with a custom bar above the global one, then a pending detection between them.
    species_overrides.set_override(Species(BLACKBIRD), auto_confirm_threshold=0.98, blacklisted=False)
    pending = create_detection(scientific_name=BLACKBIRD, confidence=0.95, validation_status=ValidationStatus.PENDING)

    # Clearing drops the bar from 0.98 back to the global 0.9, auto-confirming the 0.95 row.
    species_overrides.clear_override(Species(BLACKBIRD))

    assert override_queries.get(Species(BLACKBIRD)) is None
    assert _status(pending.id) == ValidationStatus.AUTO_CONFIRMED


def test_lowering_the_global_bar_publishes_what_was_waiting_on_it(
    create_detected_species: Callable[..., Any], create_detection: Callable[..., Any]
) -> None:
    create_detected_species(BLACKBIRD)
    above = create_detection(scientific_name=BLACKBIRD, confidence=0.85, validation_status=ValidationStatus.PENDING)
    below = create_detection(scientific_name=ROBIN, confidence=0.60, validation_status=ValidationStatus.PENDING)

    Settings.set(SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE, "0.8")
    species_overrides.clear_queue_for_global_bar(previous_bar=0.9)

    assert _status(above.id) == ValidationStatus.AUTO_CONFIRMED
    assert _status(below.id) == ValidationStatus.PENDING


def test_a_species_with_its_own_bar_ignores_the_global_one(
    create_detected_species: Callable[..., Any],
    create_detection: Callable[..., Any],
    create_override: Callable[..., Any],
) -> None:
    create_detected_species(BLACKBIRD)
    pending = create_detection(scientific_name=BLACKBIRD, confidence=0.85, validation_status=ValidationStatus.PENDING)
    create_override(scientific_name=BLACKBIRD, threshold=0.95)

    Settings.set(SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE, "0.8")
    species_overrides.clear_queue_for_global_bar(previous_bar=0.9)

    assert _status(pending.id) == ValidationStatus.PENDING


def test_raising_the_global_bar_publishes_nothing(
    create_detected_species: Callable[..., Any], create_detection: Callable[..., Any]
) -> None:
    create_detected_species(BLACKBIRD)
    pending = create_detection(scientific_name=BLACKBIRD, confidence=0.95, validation_status=ValidationStatus.PENDING)

    Settings.set(SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE, "0.98")
    species_overrides.clear_queue_for_global_bar(previous_bar=0.9)

    assert _status(pending.id) == ValidationStatus.PENDING
