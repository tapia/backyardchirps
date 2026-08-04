from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.overrides import queries as species_override_repository
from backyardchirps.features.species.entity import Species
from backyardchirps.models.detected_species import DetectedSpecies

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"


def test_upsert_and_get_round_trip(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    species = Species(BLACKBIRD)

    species_override_repository.upsert(species, auto_confirm_threshold=0.6, blacklisted=True)

    override = species_override_repository.get(species)
    assert override is not None
    assert override.auto_confirm_threshold == 0.6
    assert override.blacklisted is True


def test_upsert_replaces_existing_override(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    species = Species(BLACKBIRD)

    species_override_repository.upsert(species, auto_confirm_threshold=0.6, blacklisted=False)
    species_override_repository.upsert(species, auto_confirm_threshold=None, blacklisted=True)

    override = species_override_repository.get(species)
    assert override is not None
    assert override.auto_confirm_threshold is None
    assert override.blacklisted is True


def test_get_returns_none_without_override(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    assert species_override_repository.get(Species(BLACKBIRD)) is None


def test_upsert_raises_for_never_detected_species() -> None:
    # No DetectedSpecies row exists for this species.
    with pytest.raises(DetectedSpecies.DoesNotExist):
        species_override_repository.upsert(Species(BLACKBIRD), auto_confirm_threshold=0.5, blacklisted=False)


def test_blacklisted_helpers(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    create_detected_species(ROBIN)
    species_override_repository.upsert(Species(BLACKBIRD), auto_confirm_threshold=None, blacklisted=True)
    species_override_repository.upsert(Species(ROBIN), auto_confirm_threshold=0.5, blacklisted=False)

    assert species_override_repository.blacklisted_species() == frozenset({Species(BLACKBIRD)})
    assert species_override_repository.is_blacklisted(Species(BLACKBIRD)) is True
    assert species_override_repository.is_blacklisted(Species(ROBIN)) is False


def test_auto_confirm_threshold(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    create_detected_species(ROBIN)
    species_override_repository.upsert(Species(BLACKBIRD), auto_confirm_threshold=0.55, blacklisted=False)

    assert species_override_repository.auto_confirm_threshold(Species(BLACKBIRD)) == 0.55
    assert species_override_repository.auto_confirm_threshold(Species(ROBIN)) is None  # no override


def test_list_customized_ordered_by_most_recently_changed(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    create_detected_species(ROBIN)
    species_override_repository.upsert(Species(BLACKBIRD), auto_confirm_threshold=0.5, blacklisted=False)
    species_override_repository.upsert(Species(ROBIN), auto_confirm_threshold=0.5, blacklisted=False)
    # Re-touch the blackbird so it becomes the most recently changed.
    species_override_repository.upsert(Species(BLACKBIRD), auto_confirm_threshold=0.6, blacklisted=False)

    customized = species_override_repository.list_customized()

    assert [override.species.scientific_name for override in customized] == [BLACKBIRD, ROBIN]


def test_delete_is_idempotent(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    species = Species(BLACKBIRD)
    species_override_repository.upsert(species, auto_confirm_threshold=0.5, blacklisted=False)

    species_override_repository.delete(species)
    species_override_repository.delete(species)  # missing override is a no-op

    assert species_override_repository.get(species) is None
