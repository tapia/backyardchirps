import json
from pathlib import Path
from typing import Any

from backyardchirps.features.species.entity import Species
from backyardchirps.features.species.reference_calls import get_reference_calls

_BLACKBIRD = "Turdus merula"


def _write_pack(settings: Any, tmp_path: Path, slug: str, payload: object) -> None:
    """
    Put one species' reference calls where an installed pack would have left them.
    """
    settings.SPECIES_REFERENCE_CALLS_DIR = tmp_path / "reference_calls"
    settings.SPECIES_REFERENCE_CALLS_DIR.mkdir(exist_ok=True)
    (settings.SPECIES_REFERENCE_CALLS_DIR / f"{slug}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_reads_what_the_pack_carries(tmp_path: Path, settings: Any) -> None:
    _write_pack(
        settings,
        tmp_path,
        "turdus-merula",
        [{"url": "https://xeno-canto.org/1.mp3", "type": "song", "sex": "male", "stage": "adult", "length": "0:32"}],
    )

    assert get_reference_calls(Species(_BLACKBIRD)) == [
        {
            "url": "https://xeno-canto.org/1.mp3",
            "type": "song",
            "sex": "male",
            "stage": "adult",
            "length": "0:32",
        }
    ]


def test_missing_fields_become_none(tmp_path: Path, settings: Any) -> None:
    """
    The frontend draws a dash for a field it has nothing for, so an incomplete recording
    is worth showing rather than dropping.
    """
    _write_pack(settings, tmp_path, "turdus-merula", [{"url": "https://xeno-canto.org/1.mp3", "type": "  "}])

    assert get_reference_calls(Species(_BLACKBIRD)) == [
        {"url": "https://xeno-canto.org/1.mp3", "type": None, "sex": None, "stage": None, "length": None}
    ]


def test_species_the_pack_does_not_cover_has_none(tmp_path: Path, settings: Any) -> None:
    _write_pack(settings, tmp_path, "passer-domesticus", [{"url": "https://xeno-canto.org/1.mp3"}])

    assert get_reference_calls(Species(_BLACKBIRD)) == []


def test_no_pack_installed_has_none(tmp_path: Path, settings: Any) -> None:
    """
    A station with no pack has no directory here at all, which is a working state.
    """
    settings.SPECIES_REFERENCE_CALLS_DIR = tmp_path / "never-installed"

    assert get_reference_calls(Species(_BLACKBIRD)) == []


def test_entries_without_a_usable_address_are_dropped(tmp_path: Path, settings: Any) -> None:
    _write_pack(
        settings,
        tmp_path,
        "turdus-merula",
        [
            {"type": "song"},
            {"url": ""},
            {"url": 42},
            {"url": "http://xeno-canto.org/insecure.mp3"},
            "not a recording",
            {"url": "https://xeno-canto.org/good.mp3"},
        ],
    )

    assert [call["url"] for call in get_reference_calls(Species(_BLACKBIRD))] == ["https://xeno-canto.org/good.mp3"]


def test_at_most_five_recordings(tmp_path: Path, settings: Any) -> None:
    _write_pack(
        settings,
        tmp_path,
        "turdus-merula",
        [{"url": f"https://xeno-canto.org/{number}.mp3"} for number in range(20)],
    )

    assert len(get_reference_calls(Species(_BLACKBIRD))) == 5


def test_a_file_that_is_not_a_list_is_ignored(tmp_path: Path, settings: Any) -> None:
    _write_pack(settings, tmp_path, "turdus-merula", {"url": "https://xeno-canto.org/1.mp3"})

    assert get_reference_calls(Species(_BLACKBIRD)) == []


def test_unreadable_json_is_ignored(tmp_path: Path, settings: Any) -> None:
    settings.SPECIES_REFERENCE_CALLS_DIR = tmp_path / "reference_calls"
    settings.SPECIES_REFERENCE_CALLS_DIR.mkdir()
    (settings.SPECIES_REFERENCE_CALLS_DIR / "turdus-merula.json").write_text("{ broken", encoding="utf-8")

    assert get_reference_calls(Species(_BLACKBIRD)) == []
