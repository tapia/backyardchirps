from pathlib import Path
from typing import Any

import pytest

from backyardchirps.features.species.entity import Species
from backyardchirps.features.species.entity import UnknownSpeciesError
from backyardchirps.features.species.taxonomy import taxonomy


def test_from_scientific_name_valid() -> None:
    species = Species.from_scientific_name("Turdus merula")
    assert species is not None
    assert species.scientific_name == "Turdus merula"


def test_from_scientific_name_unknown_returns_none() -> None:
    assert Species.from_scientific_name("Nota realspecies") is None


def test_from_slug_valid() -> None:
    species = Species.from_slug("turdus-merula")
    assert species is not None
    assert species.scientific_name == "Turdus merula"


def test_from_slug_unknown_returns_none() -> None:
    assert Species.from_slug("not-a-real-slug") is None


def test_construction_with_unknown_name_raises() -> None:
    with pytest.raises(UnknownSpeciesError, match="Nota realspecies"):
        Species("Nota realspecies")


def test_slug_and_common_name_delegate_to_taxonomy() -> None:
    species = Species("Turdus merula")
    assert species.slug == "turdus-merula"
    assert species.common_name("en") == "Common Blackbird"
    assert species.common_name("es") == "Mirlo Común"


def test_is_bird_true_for_bird() -> None:
    assert Species("Turdus merula").is_bird() is True


def test_is_bird_false_for_insect() -> None:
    # Acheta domesticus (house cricket) is in BirdNET's taxonomy as an insect.
    assert Species("Acheta domesticus").is_bird() is False


def test_is_rare_none_when_no_local_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(taxonomy, "_local_species", None)
    assert Species("Turdus merula").is_rare() is None


def test_is_rare_false_for_local_species(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(taxonomy, "_local_species", {"Turdus merula"})
    assert Species("Turdus merula").is_rare() is False


def test_is_rare_true_for_non_local_species(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(taxonomy, "_local_species", {"Passer domesticus"})
    assert Species("Turdus merula").is_rare() is True


def test_map_url_points_at_the_file_the_pack_supplies(tmp_path: Path, settings: Any) -> None:
    settings.SPECIES_RANGE_MAPS_DIR = tmp_path / "range_maps"
    settings.SPECIES_RANGE_MAPS_DIR.mkdir()
    (settings.SPECIES_RANGE_MAPS_DIR / "turdus-merula.webp").write_bytes(b"not an image")

    assert Species("Turdus merula").map_url == "/species-data/range_maps/turdus-merula.webp"


def test_map_url_is_none_with_no_pack_installed(tmp_path: Path, settings: Any) -> None:
    """
    Range maps come from a pack, so a station that has not installed one has no directory
    to read at all. That has to cost the map and nothing else.
    """
    settings.SPECIES_RANGE_MAPS_DIR = tmp_path / "never-installed"

    assert Species("Turdus merula").map_url is None
