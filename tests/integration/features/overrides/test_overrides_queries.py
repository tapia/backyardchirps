from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.overrides import queries as override_queries
from backyardchirps.features.species.entity import Species
from backyardchirps.models.detected_species import DetectedSpecies

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"


def test_upsert_and_get_round_trip(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    species = Species(BLACKBIRD)

    override_queries.upsert(species, auto_confirm_threshold=0.6, blacklisted=True)

    override = override_queries.get(species)
    assert override is not None
    assert override.auto_confirm_threshold == 0.6
    assert override.blacklisted is True


def test_upsert_replaces_existing_override(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    species = Species(BLACKBIRD)

    override_queries.upsert(species, auto_confirm_threshold=0.6, blacklisted=False)
    override_queries.upsert(species, auto_confirm_threshold=None, blacklisted=True)

    override = override_queries.get(species)
    assert override is not None
    assert override.auto_confirm_threshold is None
    assert override.blacklisted is True


def test_get_returns_none_without_override(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    assert override_queries.get(Species(BLACKBIRD)) is None


def test_upsert_raises_for_never_detected_species() -> None:
    # No DetectedSpecies row exists for this species.
    with pytest.raises(DetectedSpecies.DoesNotExist):
        override_queries.upsert(Species(BLACKBIRD), auto_confirm_threshold=0.5, blacklisted=False)


def test_blacklisted_helpers(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    create_detected_species(ROBIN)
    override_queries.upsert(Species(BLACKBIRD), auto_confirm_threshold=None, blacklisted=True)
    override_queries.upsert(Species(ROBIN), auto_confirm_threshold=0.5, blacklisted=False)

    assert override_queries.blacklisted_species() == frozenset({Species(BLACKBIRD)})
    assert override_queries.is_blacklisted(Species(BLACKBIRD)) is True
    assert override_queries.is_blacklisted(Species(ROBIN)) is False


def test_auto_confirm_threshold(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    create_detected_species(ROBIN)
    override_queries.upsert(Species(BLACKBIRD), auto_confirm_threshold=0.55, blacklisted=False)

    assert override_queries.auto_confirm_threshold(Species(BLACKBIRD)) == 0.55
    assert override_queries.auto_confirm_threshold(Species(ROBIN)) is None  # no override


def test_list_customized_ordered_by_most_recently_changed(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    create_detected_species(ROBIN)
    override_queries.upsert(Species(BLACKBIRD), auto_confirm_threshold=0.5, blacklisted=False)
    override_queries.upsert(Species(ROBIN), auto_confirm_threshold=0.5, blacklisted=False)
    # Re-touch the blackbird so it becomes the most recently changed.
    override_queries.upsert(Species(BLACKBIRD), auto_confirm_threshold=0.6, blacklisted=False)

    customized = override_queries.list_customized()

    assert [override.species.scientific_name for override in customized] == [BLACKBIRD, ROBIN]


def test_delete_is_idempotent(create_detected_species: Callable[..., Any]) -> None:
    create_detected_species(BLACKBIRD)
    species = Species(BLACKBIRD)
    override_queries.upsert(species, auto_confirm_threshold=0.5, blacklisted=False)

    override_queries.delete(species)
    override_queries.delete(species)  # missing override is a no-op

    assert override_queries.get(species) is None
