from pathlib import Path
from typing import Any

import pytest

from backyardchirps.features.species.taxonomy import _normalize_for_search
from backyardchirps.features.species.taxonomy import taxonomy


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Común", "comun"),
        ("MERULA", "merula"),
        ("Pingüino", "pinguino"),
        ("Águila", "aguila"),
    ],
)
def test_normalize_for_search(text: str, expected: str) -> None:
    assert _normalize_for_search(text) == expected


def test_to_slug_and_reverse_round_trip() -> None:
    slug = taxonomy.to_slug("Turdus merula")
    assert slug == "turdus-merula"
    assert taxonomy.get_scientific_name_by_slug(slug) == "Turdus merula"


def test_get_scientific_name_by_slug_unknown_returns_none() -> None:
    assert taxonomy.get_scientific_name_by_slug("not-a-real-slug") is None


def test_search_matches_by_scientific_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    # Scoped to a known set rather than whatever list the machine happens to hold, so the
    # assertion below means the same thing everywhere.
    monkeypatch.setattr(taxonomy, "_local_species", {"Turdus merula", "Turdus philomelos", "Erithacus rubecula"})

    results = taxonomy.search("turdus", "es", max_results=10)

    scientific_names = [entry["scientific_name"] for entry in results]
    assert "Turdus merula" in scientific_names
    assert all(name.lower().startswith("turdus") for name in scientific_names)


def test_search_is_accent_insensitive() -> None:
    assert taxonomy.search("comun", "es") == taxonomy.search("común", "es")


def test_search_respects_max_results() -> None:
    assert len(taxonomy.search("a", "es", max_results=3)) == 3


def test_search_unknown_query_returns_empty() -> None:
    assert taxonomy.search("zzzznotarealbird", "es") == []


def test_get_external_links_builds_urls() -> None:
    links = taxonomy.get_external_links("Turdus merula", "es")
    assert links["ebird"] == "https://ebird.org/species/eurbla"
    assert links["seo"] == "https://seo.org/ave/mirlo-comun/"
    assert links["wikipedia"] == "https://es.wikipedia.org/wiki/Turdus%20merula"


def test_get_external_links_returns_none_for_missing_data() -> None:
    # A species with no eBird code, Wikipedia page or common name gives every link as
    # None, and never a KeyError.
    links = taxonomy.get_external_links("Nota realspecies", "es")
    assert links == {"wikipedia": None, "ebird": None, "seo": None}


def test_local_species_list_drops_names_the_taxonomy_does_not_know(tmp_path: Path, settings: Any) -> None:
    """
    A station's list is built separately from the taxonomy, so it can still name a species
    renamed since. Dropping those on load is what keeps search from offering a name that
    Species() then refuses to build, and keeps a renamed local bird from reading as rare.
    """
    species_file = tmp_path / "species_birdnet.txt"
    species_file.write_text("# a comment\nTurdus merula\nNotarealus fakebirdus\n")
    settings.SPECIES_LIST_RUNTIME_FILE = species_file

    assert taxonomy._load_local_species() == {"Turdus merula"}


def test_no_species_list_is_a_working_state(tmp_path: Path, settings: Any) -> None:
    """
    Nothing ships a list, so this is how every station starts. Search then covers the whole
    taxonomy and nothing is reported as rare.
    """
    settings.SPECIES_LIST_RUNTIME_FILE = tmp_path / "not-generated-yet.txt"

    assert taxonomy._load_local_species() is None
