from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from backyardchirps.features.species.taxonomy import taxonomy


class UnknownSpeciesError(ValueError):
    """
    Raised when a Species is built from a scientific name the BirdNET taxonomy does not
    have.
    """


@dataclass(frozen=True)
class Species:
    """
    A species from the BirdNET taxonomy.

    Building one checks the scientific name against the taxonomy, so holding a Species
    is itself proof that the name is a real one.
    """

    scientific_name: str

    def __post_init__(self) -> None:
        if not taxonomy.knows(self.scientific_name):
            raise UnknownSpeciesError(f"Unknown species: {self.scientific_name!r}")

    @classmethod
    def from_scientific_name(cls, scientific_name: str) -> Species | None:
        if not taxonomy.knows(scientific_name):
            return None
        return cls(scientific_name)

    @classmethod
    def from_slug(cls, slug: str) -> Species | None:
        scientific_name = taxonomy.get_scientific_name_by_slug(slug)
        if scientific_name is None:
            return None
        return cls(scientific_name)

    @classmethod
    def search(cls, query: str, language: str, max_results: int = 30) -> list[dict]:
        results = taxonomy.search(query, language, max_results)
        return [
            {
                **entry,
                "slug": taxonomy.to_slug(entry["scientific_name"]),
                "image_url": cls(entry["scientific_name"]).image_url,
            }
            for entry in results
        ]

    @property
    def slug(self) -> str:
        return taxonomy.to_slug(self.scientific_name)

    def common_name(self, language: str) -> str:
        return taxonomy.get_common_name(self.scientific_name, language)

    def description(self, language: str) -> str:
        return taxonomy.get_description(self.scientific_name, language)

    def external_links(self, language: str) -> dict[str, str | None]:
        return taxonomy.get_external_links(self.scientific_name, language)

    def ebird_code(self) -> str | None:
        return taxonomy.get_ebird_code(self.scientific_name)

    def is_bird(self) -> bool:
        """
        BirdNET's taxonomy also covers insects, mammals, amphibians and reptiles. The
        recorder uses this to keep them out of the detections.
        """
        return taxonomy.get_taxon_group(self.scientific_name) == "Aves"

    def is_rare(self) -> bool | None:
        """
        True when the species is missing from the local species list, and so not
        expected around here. None when no local list has been generated yet, which is
        not the same as the species being common.
        """
        is_local = taxonomy.is_local(self.scientific_name)
        if is_local is None:
            return None
        return not is_local

    @property
    def image_path(self) -> Path | None:
        path = settings.SPECIES_IMAGES_DIR / f"{self.slug}.jpg"
        return path if path.exists() else None

    @property
    def image_url(self) -> str:
        path = self.image_path
        if path:
            return f"/species-data/images/{path.name}"
        return f"https://birdnet.cornell.edu/taxonomy/api/image/{self.scientific_name}"

    @property
    def map_url(self) -> str | None:
        path = settings.SPECIES_RANGE_MAPS_DIR / f"{self.slug}.webp"
        if not path.exists():
            return None
        return f"/species-data/range_maps/{path.name}"
