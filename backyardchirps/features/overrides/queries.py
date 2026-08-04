from backyardchirps.features.overrides.entity import SpeciesOverride
from backyardchirps.features.species.entity import Species
from backyardchirps.models.detected_species import DetectedSpecies
from backyardchirps.models.stored_species_override import StoredSpeciesOverride


def get(species: Species) -> SpeciesOverride | None:
    """
    None when the species has not been customized.
    """
    stored = (
        StoredSpeciesOverride.objects.select_related("species")
        .filter(species__scientific_name=species.scientific_name)
        .first()
    )
    return stored.to_entity() if stored is not None else None


def list_customized() -> list[SpeciesOverride]:
    """
    Every species override, blacklisted or with a custom threshold, most recently changed
    first.
    """
    overrides = [
        stored.to_entity() for stored in StoredSpeciesOverride.objects.select_related("species").order_by("-updated_at")
    ]
    return [override for override in overrides if override is not None]


def blacklisted_species() -> frozenset[Species]:
    """
    The blacklisted species, for filtering objects already in memory. Code reading from
    the database should join on the override instead of calling this.

    Read fresh every time, so the recorder picks up blacklist changes without a restart.
    """
    species_set = set()
    for stored in StoredSpeciesOverride.objects.select_related("species").filter(blacklisted=True):
        species = stored.species.to_entity()
        if species is not None:
            species_set.add(species)
    return frozenset(species_set)


def is_blacklisted(species: Species) -> bool:
    """
    Read fresh every time, so blacklist changes take effect without a restart.
    """
    return StoredSpeciesOverride.objects.filter(
        species__scientific_name=species.scientific_name, blacklisted=True
    ).exists()


def auto_confirm_threshold(species: Species) -> float | None:
    """
    None when the species has no threshold of its own and follows the global bar. Read
    fresh every time, so changes take effect without a restart.
    """
    return (
        StoredSpeciesOverride.objects.filter(species__scientific_name=species.scientific_name)
        .values_list("auto_confirm_threshold", flat=True)
        .first()
    )


def upsert(species: Species, auto_confirm_threshold: float | None, blacklisted: bool) -> SpeciesOverride:
    """
    Create or replace the override for the species.

    Raises DetectedSpecies.DoesNotExist when the species has never been detected.
    """
    detected_species = DetectedSpecies.objects.get(scientific_name=species.scientific_name)
    stored, _ = StoredSpeciesOverride.objects.update_or_create(
        species=detected_species,
        defaults={"auto_confirm_threshold": auto_confirm_threshold, "blacklisted": blacklisted},
    )
    override = stored.to_entity()
    assert override is not None  # a Species was passed in, so the taxonomy knows it
    return override


def delete(species: Species) -> None:
    """
    Put the species back on the global defaults. Deleting an override that is not there
    does nothing.
    """
    StoredSpeciesOverride.objects.filter(species__scientific_name=species.scientific_name).delete()
