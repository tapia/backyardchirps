"""
Installing a region pack: what a station reads afterwards, and what survives a failure.

The archives here are built the way the pack builder builds one, a directory holding
pack.json beside ebird_occurrence, range_maps and reference_calls, so what is under test
is the layout a real pack has rather than one invented for the test.
"""

import hashlib
import json
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings

from backyardchirps.features.region_packs import logic as region_packs_logic
from backyardchirps.features.region_packs.entity import BoundingBox
from backyardchirps.features.region_packs.entity import RegionPack
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey

pytestmark = pytest.mark.django_db


@pytest.fixture
def data_dir(tmp_path: Path, settings: Any) -> Path:
    """
    A station's data directory: where packs are unpacked, and where the links a station
    reads through live.
    """
    settings.REGION_PACKS_DIR = tmp_path / "region-packs"
    settings.SPECIES_RUNTIME_DIR = tmp_path / "species"
    return tmp_path


def _build_archive(
    tmp_path: Path,
    pack_id: str,
    *,
    species: str = "barswa",
    with_maps: bool = True,
    version: str = "2026-08-16",
) -> Path:
    staging = tmp_path / "staging" / pack_id
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "ebird_occurrence" / species).mkdir(parents=True)
    (staging / "ebird_occurrence" / species / "band-dates.csv").write_text("band,date\n1,2023-01-04\n")
    (staging / "ebird_occurrence" / species / f"{species}_occurrence_median_9km_2023.tif").write_bytes(b"not a raster")
    maps = staging / "range_maps"
    maps.mkdir()
    if with_maps:
        (maps / "hirundo-rustica.webp").write_bytes(b"not an image")
    calls = staging / "reference_calls"
    calls.mkdir()
    (calls / "hirundo-rustica.json").write_text(json.dumps([{"url": "https://xeno-canto.org/1.mp3"}]))
    (staging / "pack.json").write_text(
        json.dumps({"id": pack_id, "names": {"en": "A region"}, "version": version, "species_count": 1})
    )

    archive = tmp_path / f"{pack_id}-{version}.tar.zst"
    subprocess.run(
        ["tar", "--zstd", "-cf", str(archive), "-C", str(staging.parent), pack_id],
        check=True,
    )
    return archive


def _pack_for(archive: Path, pack_id: str = "a-region", version: str = "2026-08-16") -> RegionPack:
    return RegionPack(
        id=pack_id,
        names={"en": "A region"},
        bbox=BoundingBox(west=-10.0, south=35.0, east=4.5, north=44.5),
        version=version,
        species_count=1,
        url=f"file://{archive}",
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        size_bytes=archive.stat().st_size,
    )


@pytest.fixture
def serve_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Copy the archive instead of fetching it, so these tests never touch the network. What
    the real download adds is streaming and a progress count, neither of which changes
    what ends up on disk.
    """

    def _download(url: str, destination: Path, on_progress: Any = None) -> None:
        source = Path(url.removeprefix("file://"))
        destination.write_bytes(source.read_bytes())

    monkeypatch.setattr(region_packs_logic.region_packs, "download_pack", _download)


def test_a_station_reads_the_pack_through_links_it_already_had(
    tmp_path: Path, data_dir: Path, serve_locally: None
) -> None:
    """
    The point of the symlinks: the paths in settings never change, so nothing has to be
    told which pack is in use, and switching one is moving a link.
    """
    archive = _build_archive(tmp_path, "a-region")

    region_packs_logic.install(_pack_for(archive))

    rasters = Path(settings.SPECIES_RUNTIME_DIR) / "ebird_occurrence"
    assert rasters.is_symlink()
    assert (rasters / "barswa" / "band-dates.csv").read_text().startswith("band,date")
    assert (Path(settings.SPECIES_RUNTIME_DIR) / "range_maps").is_symlink()

    calls = Path(settings.SPECIES_RUNTIME_DIR) / "reference_calls"
    assert calls.is_symlink()
    assert json.loads((calls / "hirundo-rustica.json").read_text())[0]["url"].startswith("https://")


def test_the_paths_the_app_reads_are_the_ones_an_install_links() -> None:
    """
    The seam between a pack and the pages that read one. Both sides name the directory as a
    string, in different files, so a rename on one side would leave a link nothing reads and a
    setting pointing at nothing, with every test still passing.
    """
    linked = set(region_packs_logic.LINKED_DIRECTORIES)
    assert Path(settings.SPECIES_RANGE_MAPS_DIR).name in linked
    assert Path(settings.SPECIES_REFERENCE_CALLS_DIR).name in linked
    assert Path(settings.EBIRD_DATA_DIR).name in linked


def test_the_installed_pack_is_recorded(tmp_path: Path, data_dir: Path, serve_locally: None) -> None:
    archive = _build_archive(tmp_path, "a-region")

    region_packs_logic.install(_pack_for(archive))

    assert Settings.get(SettingsKey.REGION_PACK) == "a-region"
    assert region_packs_logic.pack_is_installed() is True
    assert region_packs_logic.installed_region_pack_version() == "2026-08-16"


def test_reinstalling_a_pack_brings_what_the_newer_build_added(
    tmp_path: Path, data_dir: Path, serve_locally: None
) -> None:
    """
    How a station that already has a pack gets data added to it later, which is the only
    route reference calls have onto a station installed before packs carried them.
    """
    region_packs_logic.install(_pack_for(_build_archive(tmp_path, "a-region", version="2026-08-16")))
    calls = Path(settings.SPECIES_RUNTIME_DIR) / "reference_calls"
    (Path(settings.REGION_PACKS_DIR) / "a-region" / "reference_calls" / "hirundo-rustica.json").unlink()
    assert not (calls / "hirundo-rustica.json").exists()

    rebuilt = _build_archive(tmp_path, "a-region", version="2026-09-01")
    region_packs_logic.install(_pack_for(rebuilt, version="2026-09-01"))

    assert (calls / "hirundo-rustica.json").is_file()
    assert region_packs_logic.installed_region_pack_version() == "2026-09-01"


def test_the_version_is_empty_when_there_is_no_pack_to_read(data_dir: Path) -> None:
    """
    Nothing to compare with the index, which the settings page reads as no update waiting
    rather than as one.
    """
    assert region_packs_logic.installed_region_pack_version() == ""

    Settings.set(SettingsKey.REGION_PACK, "a-region")
    assert region_packs_logic.installed_region_pack_version() == ""


def test_a_recorded_pack_that_is_not_on_disk_is_not_installed(data_dir: Path) -> None:
    """
    A database restored onto a fresh card brings the setting and not the pack.
    """
    Settings.set(SettingsKey.REGION_PACK, "a-region")

    assert region_packs_logic.installed_region_pack_id() == "a-region"
    assert region_packs_logic.pack_is_installed() is False


def test_a_pack_that_does_not_match_its_checksum_is_refused(
    tmp_path: Path, data_dir: Path, serve_locally: None
) -> None:
    archive = _build_archive(tmp_path, "a-region")
    lying = _pack_for(archive)
    object.__setattr__(lying, "sha256", "0" * 64)

    with pytest.raises(region_packs_logic.RegionPackError, match="checksum"):
        region_packs_logic.install(lying)

    assert Settings.get(SettingsKey.REGION_PACK) == ""
    assert not (Path(settings.SPECIES_RUNTIME_DIR) / "ebird_occurrence").exists()


def test_a_failed_install_leaves_the_pack_that_was_working(tmp_path: Path, data_dir: Path, serve_locally: None) -> None:
    """
    The reason everything happens beside the real location first. A station that loses a
    working pack to a bad download is worse off than one that never tried.
    """
    good = _build_archive(tmp_path, "a-region")
    region_packs_logic.install(_pack_for(good))

    broken = tmp_path / "broken.tar.zst"
    broken.write_bytes(b"not an archive at all")
    second = _pack_for(broken, pack_id="another-region")

    with pytest.raises(region_packs_logic.RegionPackError):
        region_packs_logic.install(second)

    assert Settings.get(SettingsKey.REGION_PACK) == "a-region"
    rasters = Path(settings.SPECIES_RUNTIME_DIR) / "ebird_occurrence"
    assert (rasters / "barswa" / "band-dates.csv").is_file()


def test_switching_packs_moves_the_links(tmp_path: Path, data_dir: Path, serve_locally: None) -> None:
    first = _build_archive(tmp_path, "a-region", species="barswa")
    second = _build_archive(tmp_path, "another-region", species="eurbla")

    region_packs_logic.install(_pack_for(first))
    region_packs_logic.install(_pack_for(second, pack_id="another-region"))

    rasters = Path(settings.SPECIES_RUNTIME_DIR) / "ebird_occurrence"
    assert (rasters / "eurbla").is_dir()
    assert not (rasters / "barswa").exists()
    assert Settings.get(SettingsKey.REGION_PACK) == "another-region"
    # The pack it replaced is still on disk, so going back does not mean downloading again.
    assert (Path(settings.REGION_PACKS_DIR) / "a-region").is_dir()


def test_rasters_downloaded_before_packs_existed_are_moved_aside_not_deleted(
    tmp_path: Path, data_dir: Path, serve_locally: None
) -> None:
    """
    A station that has been running since before packs holds gigabytes of whole-world
    rasters at exactly the path the link wants. They are not ours to delete.
    """
    rasters = Path(settings.SPECIES_RUNTIME_DIR) / "ebird_occurrence"
    rasters.mkdir(parents=True)
    (rasters / "keep-me.txt").write_text("2.7 gigabytes, pretend")

    region_packs_logic.install(_pack_for(_build_archive(tmp_path, "a-region")))

    superseded = Path(settings.SPECIES_RUNTIME_DIR) / "ebird_occurrence.superseded"
    assert (superseded / "keep-me.txt").is_file()
    assert rasters.is_symlink()


def test_an_archive_holding_no_pack_json_is_refused(tmp_path: Path, data_dir: Path, serve_locally: None) -> None:
    staging = tmp_path / "junk" / "a-region"
    staging.mkdir(parents=True)
    (staging / "something.txt").write_text("not a pack")
    archive = tmp_path / "junk.tar.zst"
    subprocess.run(["tar", "--zstd", "-cf", str(archive), "-C", str(staging.parent), "a-region"], check=True)

    with pytest.raises(region_packs_logic.RegionPackError, match=r"pack\.json"):
        region_packs_logic.install(_pack_for(archive))


def test_an_archive_climbing_out_of_its_directory_is_refused(
    tmp_path: Path, data_dir: Path, serve_locally: None
) -> None:
    """
    A pack is a large file from the internet unpacked by a service account. Without the
    data filter it could write anywhere that account can reach.
    """
    plain = tmp_path / "escaping.tar"
    outside = tmp_path / "outside.txt"
    outside.write_text("should never be written by an unpack")
    with tarfile.open(plain, "w") as tar:
        tar.add(outside, arcname="../escaped.txt")
    escaping = tmp_path / "escaping.tar.zst"
    subprocess.run(["zstd", "-q", "-o", str(escaping), str(plain)], check=True)

    with pytest.raises(region_packs_logic.RegionPackError, match="archive"):
        region_packs_logic.install(_pack_for(escaping))

    assert not (tmp_path / "escaped.txt").exists()
