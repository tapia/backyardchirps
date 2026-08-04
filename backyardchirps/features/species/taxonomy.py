import json
import logging
import unicodedata
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)


def _runtime_or_seed(runtime_path: str | Path, seed_path: str | Path) -> Path:
    """
    Use the file update_species_data regenerated when it is there, and the seed that
    ships in the repo when it is not.
    """
    runtime = Path(runtime_path)
    return runtime if runtime.exists() else Path(seed_path)


def _normalize_for_search(text: str) -> str:
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("ascii").lower()


def _seo_slug(name: str) -> str:
    normalized = unicodedata.normalize("NFD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_name.lower().replace(" ", "-")


class Taxonomy:
    def __init__(self):
        taxonomy_path = _runtime_or_seed(settings.SPECIES_TAXONOMY_RUNTIME_FILE, settings.SPECIES_TAXONOMY_FILE)
        with open(taxonomy_path) as f:
            taxa = json.load(f)

        self._common_names: dict[str, dict[str, str]] = {}
        self._descriptions: dict[str, dict[str, str]] = {}
        self._ebird_codes: dict[str, str] = {}
        self._wikipedia_urls: dict[str, dict[str, str]] = {}
        self._scientific_name_by_slug: dict[str, str] = {}
        self._taxon_groups: dict[str, str] = {}

        for taxon in taxa:
            scientific_name = taxon["scientific_name"]
            self._scientific_name_by_slug[self.to_slug(scientific_name)] = scientific_name
            self._common_names[scientific_name] = taxon["common_names"]
            self._descriptions[scientific_name] = taxon.get("descriptions") or {}
            if taxon.get("taxon_group"):
                self._taxon_groups[scientific_name] = taxon["taxon_group"]
            if taxon.get("ebird_code"):
                self._ebird_codes[scientific_name] = taxon["ebird_code"]
            if taxon.get("wikipedia_urls"):
                self._wikipedia_urls[scientific_name] = taxon["wikipedia_urls"]

        self._local_species: set[str] | None = self._load_local_species()

    def knows(self, scientific_name: str) -> bool:
        return scientific_name in self._common_names

    def to_slug(self, scientific_name: str) -> str:
        return scientific_name.lower().replace(" ", "-")

    def get_scientific_name_by_slug(self, slug: str) -> str | None:
        return self._scientific_name_by_slug.get(slug)

    def get_common_name(self, scientific_name: str, language: str) -> str:
        return self._common_names.get(scientific_name, {}).get(language, scientific_name)

    def get_description(self, scientific_name: str, language: str) -> str:
        return self._descriptions.get(scientific_name, {}).get(language, "")

    def get_ebird_code(self, scientific_name: str) -> str | None:
        return self._ebird_codes.get(scientific_name)

    def get_taxon_group(self, scientific_name: str) -> str | None:
        """
        One of Aves, Mammalia, Insecta, Amphibia or Reptilia. None when the taxonomy
        does not say.
        """
        return self._taxon_groups.get(scientific_name)

    def get_wikipedia_url(self, scientific_name: str, language: str) -> str | None:
        urls = self._wikipedia_urls.get(scientific_name, {})
        return urls.get(language) or urls.get("en")

    def get_external_links(self, scientific_name: str, language: str) -> dict[str, str | None]:
        ebird_code = self._ebird_codes.get(scientific_name)
        spanish_name = self._common_names.get(scientific_name, {}).get("es")

        ebird_url = f"https://ebird.org/species/{ebird_code}" if ebird_code else None

        seo_url = None
        if spanish_name:
            seo_url = f"https://seo.org/ave/{_seo_slug(spanish_name)}/"

        return {
            "wikipedia": self.get_wikipedia_url(scientific_name, language),
            "ebird": ebird_url,
            "seo": seo_url,
        }

    def is_local(self, scientific_name: str) -> bool | None:
        """
        None means no local list was loaded, so we cannot say either way.
        """
        if self._local_species is None:
            return None
        return scientific_name in self._local_species

    def search(self, query: str, language: str, max_results: int = 30) -> list[dict]:
        normalized_query = _normalize_for_search(query)
        searchable_names = self._local_species if self._local_species is not None else self._common_names.keys()

        starts_with_results = []
        contains_results = []

        for scientific_name in searchable_names:
            common_names = self._common_names.get(scientific_name, {})
            common_name = common_names.get(language) or common_names.get("en") or scientific_name
            normalized_common_name = _normalize_for_search(common_name)
            normalized_scientific_name = _normalize_for_search(scientific_name)

            if normalized_common_name.startswith(normalized_query) or normalized_scientific_name.startswith(
                normalized_query
            ):
                starts_with_results.append({"scientific_name": scientific_name, "common_name": common_name})
            elif normalized_query in normalized_common_name or normalized_query in normalized_scientific_name:
                contains_results.append({"scientific_name": scientific_name, "common_name": common_name})

        return (starts_with_results + contains_results)[:max_results]

    def _load_local_species(self) -> set[str] | None:
        species_list_path = Path(settings.SPECIES_LIST_RUNTIME_FILE)
        if not species_list_path.exists():
            # Nothing ships one, so this is the normal state until update_species_data has
            # built it from the station's coordinates.
            logger.info("No species list yet at %s, so search covers the whole taxonomy", species_list_path)
            return None

        local_scientific_names = set()
        unknown_scientific_names = set()
        with open(species_list_path) as species_file:
            for raw_line in species_file:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                scientific_name = line.split("_")[0].strip()
                if not scientific_name:
                    continue
                # The list and the taxonomy are produced separately and drift apart as
                # species get renamed. Keeping a name the taxonomy has dropped breaks two
                # things: search offers it and Species() then refuses to build it, and the
                # species under its current name reads as rare, because that name is not
                # in here.
                if self.knows(scientific_name):
                    local_scientific_names.add(scientific_name)
                else:
                    unknown_scientific_names.add(scientific_name)

        if unknown_scientific_names:
            logger.warning(
                "Ignoring %d species in %s that the taxonomy no longer knows, most likely "
                "renamed since the list was generated: %s",
                len(unknown_scientific_names),
                species_list_path,
                ", ".join(sorted(unknown_scientific_names)),
            )

        logger.info(
            "Loaded %d local species from %s",
            len(local_scientific_names),
            species_list_path,
        )
        return local_scientific_names or None


taxonomy = Taxonomy()
