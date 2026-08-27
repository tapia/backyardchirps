import hashlib
import json
import logging
import os
import shutil
import subprocess
import tarfile
import tempfile
import threading
from collections.abc import Callable
from functools import partial
from pathlib import Path

import requests
from django.conf import settings
from django.db import connection

from backyardchirps.features.region_packs import install_status
from backyardchirps.features.region_packs.entity import RegionPack
from backyardchirps.features.region_packs.entity import RegionPackChoice
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.species import seasonality
from backyardchirps.integrations import region_packs

logger = logging.getLogger(__name__)

# What a station reads a pack through. Each is a symlink inside the data directory whose
# target moves when a pack is installed, which is why nothing in settings.py has to know
# which pack is in use: the paths never change, only what they point at. It is the same
# trick as the releases/current symlink, for the same reason.
LINKED_DIRECTORIES = ("ebird_occurrence", "range_maps", "reference_calls")

# Where somebody no pack covers is sent. A miss that nobody hears about is a pack that
# never gets built, so the wizard and the settings page both offer this.
REGION_PACK_REQUEST_URL = "https://github.com/tapia/backyardchirps-regional-packs/issues/new?template=new-pack.yml"


class RegionPackError(Exception):
    """
    Installing a pack failed in a way worth showing to whoever asked for it.
    """


class RegionPackSuperseded(Exception):
    """
    The pack being downloaded is no longer the one the station is meant to end up with,
    because somebody chose a different one while it was running. Not a failure: the
    download is dropped and the chosen pack is fetched instead.
    """


def choose_for(latitude: float, longitude: float) -> RegionPackChoice:
    """
    The pack covering these coordinates, or the nearest one when none does.

    A miss is answered with the nearest rather than with nothing, because "no pack covers
    you, the nearest is 400km away" is what turns somebody's disappointment into a request
    for a pack that ought to exist.
    """
    return choose_from(available_packs(), latitude, longitude)


def choose_from(packs: list[RegionPack], latitude: float, longitude: float) -> RegionPackChoice:
    """
    The same choice, made from an index the caller already has. The wizard's pack step
    lists every pack and marks one of them, so it would otherwise read the index twice to
    draw a single page.
    """
    if not packs:
        return RegionPackChoice(region_pack=None, covers=False, distance_km=None)

    nearest = min(packs, key=lambda pack: pack.bbox.distance_from(latitude, longitude))
    distance = nearest.bbox.distance_from(latitude, longitude)
    return RegionPackChoice(region_pack=nearest, covers=distance == 0.0, distance_km=distance)


def available_packs() -> list[RegionPack]:
    """
    Every pack the index lists, skipping any entry this version cannot read. A pack added
    later with a field we do not understand should cost us that pack, not the whole list.
    """
    understood = []
    for entry in region_packs.fetch_index():
        try:
            understood.append(RegionPack.from_index(entry))
        except (KeyError, TypeError, ValueError):
            logger.warning("Skipping a region pack index entry that could not be read: %r", entry)
    return understood


def installed_region_pack_id() -> str:
    """
    The id of the installed pack, or an empty string. What is recorded, not what is on
    disk: see pack_is_installed.
    """
    return str(Settings.get(SettingsKey.REGION_PACK))


def pack_is_installed() -> bool:
    """
    Whether the recorded pack is actually unpacked and linked. The two can disagree after
    a restore from backup that brought the database but not the data directory.
    """
    pack_id = installed_region_pack_id()
    if not pack_id:
        return False
    return (Path(settings.REGION_PACKS_DIR) / pack_id).is_dir()


def installed_region_pack_version() -> str:
    """
    The version of the pack on disk, or an empty string when there is none to read.

    Read from the pack itself rather than recorded when it was installed, because it
    describes what a station can actually serve. A pack rebuilt under the same id is a
    new version of the same pack, and comparing this with the index is how a station
    finds out it is holding an old one.
    """
    pack_id = installed_region_pack_id()
    if not pack_id:
        return ""

    manifest = Path(settings.REGION_PACKS_DIR) / pack_id / "pack.json"
    try:
        described = json.loads(manifest.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ""
    except (OSError, ValueError):
        logger.warning("The pack.json of %s could not be read", pack_id, exc_info=True)
        return ""

    version = described.get("version") if isinstance(described, dict) else None
    return str(version) if isinstance(version, str) else ""


def install(pack: RegionPack, on_progress: Callable[[int, int], None] | None = None) -> None:
    """
    Download a pack, check it, unpack it, and point the station at it.

    Nothing the station reads changes until the last step. The download and the unpack
    both happen beside the real location, so a failure at any point leaves the pack that
    was in use exactly where it was, and a station that has never had one keeps reading
    what ships in the release.
    """
    packs_dir = Path(settings.REGION_PACKS_DIR)
    packs_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=packs_dir) as staging:
        archive = Path(staging) / f"{pack.id}.tar.zst"
        try:
            region_packs.download_pack(pack.url, archive, on_progress)
        except RegionPackSuperseded:
            # Not a failed download but an abandoned one, and the caller has to be able to
            # tell them apart.
            raise
        except Exception as error:
            raise RegionPackError(f"The pack could not be downloaded: {error}") from error

        _check_the_download(archive, pack)
        unpacked = _unpack(archive, Path(staging))
        _put_in_place(unpacked, packs_dir / pack.id)

    _point_the_station_at(packs_dir / pack.id)
    Settings.set(SettingsKey.REGION_PACK, pack.id)
    logger.info("Region pack %s %s installed", pack.id, pack.version)


def start_install(pack: RegionPack) -> bool:
    """
    Begin installing a pack in the background, and say whether this call is the one that
    started it. Refuses while another install is running.

    It runs in a thread rather than in the request because a pack takes minutes on a Pi,
    and the wizard is built so that nothing about the flow lives in a browser. A phone
    that locks its screen, or a tab closed by accident, must not cost somebody the
    download. Progress goes to a file, which is also how the caller finds out it finished.
    """
    if install_status.is_running():
        return False

    _begin_installing(pack)
    return True


def replace_install(pack: RegionPack) -> None:
    """
    Make this the pack the station is installing, taking over from any download already
    running.

    Somebody who walks back through the wizard and picks a different pack has to end up
    with the one they chose last. A download under way notices at its next chunk that it
    is fetching a pack nobody wants, drops it, and goes on to this one, so nothing here
    waits for it to stop.
    """
    install_status.wanted(pack.id)
    if install_status.is_running():
        return
    _begin_installing(pack)


def install_the_wanted_pack(pack: RegionPack) -> None:
    """
    Install this pack, and then whichever pack the station has been told it wants since.

    What the background thread runs, so nothing may escape it: a thread that raised would
    leave the status file saying "running" for ever, and the page watching it would never
    be told anything. Every outcome goes to the status file instead.

    It loops because the choice can change while a download is running. A thread that
    finds itself fetching a pack nobody wants any more carries on with the one that is
    wanted, rather than leaving the station holding whichever pack was chosen first.
    """
    next_pack: RegionPack | None = pack
    try:
        while next_pack is not None:
            next_pack = _install_one(next_pack)
    finally:
        connection.close()


def _begin_installing(pack: RegionPack) -> None:
    """
    Record the pack as both wanted and running, and put a thread on it.
    """
    install_status.wanted(pack.id)
    install_status.started(pack.id, pack.size_bytes)
    thread = threading.Thread(target=install_the_wanted_pack, args=(pack,), daemon=True, name=f"install-{pack.id}")
    thread.start()


def _install_one(pack: RegionPack) -> RegionPack | None:
    """
    Install one pack, report how it went, and give back the pack to install after it, or
    None when there is nothing left to do.
    """
    try:
        install(pack, on_progress=partial(_report_progress, pack))
    except RegionPackSuperseded:
        logger.info("Region pack %s was dropped for another choice", pack.id)
        return _the_pack_now_wanted()
    except RegionPackError as error:
        logger.warning("Region pack %s could not be installed: %s", pack.id, error)
        install_status.failed(pack.id, str(error))
        return None
    except Exception:
        logger.exception("Region pack %s could not be installed", pack.id)
        install_status.failed(pack.id, "unexpected")
        return None

    # A choice made in the last moments of a download, after the final chunk was reported
    # and so too late to be noticed there. The pack asked for last still wins.
    if install_status.wanted_pack_id() not in ("", pack.id):
        return _the_pack_now_wanted()
    install_status.finished(pack.id)
    return None


def _report_progress(pack: RegionPack, received_bytes: int, total_bytes: int) -> None:
    """
    Say how far the download has got, and give it up once the station has been told to
    install a different pack. Called on every chunk, which is what makes a switch take
    effect in about a megabyte rather than at the end of a download nobody wants.
    """
    if install_status.wanted_pack_id() not in ("", pack.id):
        raise RegionPackSuperseded(pack.id)
    install_status.progressed(pack.id, received_bytes, total_bytes or pack.size_bytes)


def _the_pack_now_wanted() -> RegionPack | None:
    """
    The pack the station is meant to install now, ready to download, or None when there is
    nothing to go on with.

    Every refusal is reported, because this is the only thread left: one that walks away
    quietly would leave the status file saying an install is running when none is.
    """
    wanted = install_status.wanted_pack_id()
    if not wanted:
        install_status.failed("", "no_pack_wanted")
        return None

    try:
        packs = available_packs()
    except (requests.RequestException, ValueError):
        logger.warning("Could not read the region pack index from %s", region_packs.INDEX_URL, exc_info=True)
        install_status.failed(wanted, "index_unavailable")
        return None

    chosen = next((pack for pack in packs if pack.id == wanted), None)
    if chosen is None:
        install_status.failed(wanted, "unknown_pack")
        return None

    install_status.started(chosen.id, chosen.size_bytes)
    return chosen


def _check_the_download(archive: Path, pack: RegionPack) -> None:
    """
    A pack is a large file from the internet that is about to be unpacked as an archive,
    so it is checked before anything reads it as one.
    """
    with archive.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    if digest != pack.sha256:
        raise RegionPackError("The downloaded pack does not match the checksum the index gave for it.")


def _unpack(archive: Path, staging: Path) -> Path:
    """
    Unpack into the staging directory and return the pack directory inside it.
    """
    unpacked_into = staging / "unpacked"
    _extract(archive, unpacked_into)

    directories = [entry for entry in unpacked_into.iterdir() if entry.is_dir()]
    if len(directories) != 1:
        raise RegionPackError("A pack has to hold exactly one directory.")
    if not (directories[0] / "pack.json").is_file():
        raise RegionPackError("The pack has no pack.json, so it is not a pack.")
    return directories[0]


def _extract(archive: Path, destination: Path) -> None:
    """
    Decompress with the zstd command and read the tar in Python.

    Split in two because neither half can do the other's job. Python's tarfile only learns
    zstd in 3.14 and a station runs 3.13, so the decompression has to be the zstd binary
    that install.sh already puts on the machine. The tar itself stays in Python for the
    data filter, which refuses absolute paths, entries climbing out with .., links
    pointing outside, and anything that is not a plain file or directory. A pack is a large
    file from the internet unpacked by an account that can write the whole data directory,
    so that filter is the difference between an archive and an intruder.

    Nothing is written to disk twice: zstd streams into the tar reader.
    """
    destination.mkdir(parents=True, exist_ok=True)
    try:
        decompress = subprocess.Popen(
            ["zstd", "--decompress", "--stdout", str(archive)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        raise RegionPackError("zstd is not installed, so a pack cannot be unpacked.") from None

    with decompress:
        try:
            # r| rather than r:, because a pipe cannot be seeked.
            with tarfile.open(fileobj=decompress.stdout, mode="r|") as tar:
                tar.extractall(destination, filter="data")
        except tarfile.TarError as error:
            decompress.kill()
            raise RegionPackError(f"The pack is not an archive this can read: {error}") from error

    if decompress.returncode != 0:
        raise RegionPackError("The pack could not be decompressed.")


def _put_in_place(unpacked: Path, destination: Path) -> None:
    """
    Move the unpacked pack to where it will live, replacing an older copy of the same
    pack. The move is within one filesystem, since staging sits inside REGION_PACKS_DIR, so it
    does not copy the whole pack a second time.
    """
    if destination.exists():
        superseded = destination.with_name(destination.name + ".superseded")
        shutil.rmtree(superseded, ignore_errors=True)
        os.rename(destination, superseded)
        os.rename(unpacked, destination)
        shutil.rmtree(superseded, ignore_errors=True)
        return
    os.rename(unpacked, destination)


def _point_the_station_at(pack_dir: Path) -> None:
    """
    Move the symlinks the station reads through, then drop the cached rasters.

    Each link is written beside its own place and renamed over it, so a reader never sees
    a moment with no link at all. seasonality.py keeps a predictor holding open raster
    files, and those are now the wrong pack's, so it is closed here rather than left to
    answer from files that have been replaced underneath it.
    """
    runtime_dir = Path(settings.SPECIES_RUNTIME_DIR)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    for name in LINKED_DIRECTORIES:
        target = pack_dir / name
        if not target.is_dir():
            logger.warning("Region pack %s has no %s, so that link was left alone", pack_dir.name, name)
            continue
        _replace_link(runtime_dir / name, target)

    seasonality.reset_predictor()


def _replace_link(link: Path, target: Path) -> None:
    """
    Point a link at a new target, atomically.

    A real directory here is not ours to delete. It is what a station downloaded before
    packs existed, gigabytes of whole-world rasters, so it is moved aside and named rather
    than removed, and its owner can free the space once they trust the pack.
    """
    if link.exists() and not link.is_symlink():
        superseded = link.with_name(link.name + ".superseded")
        if superseded.exists():
            logger.warning("Leaving %s alone: %s is already there", link, superseded)
            return
        os.rename(link, superseded)
        logger.warning("Moved %s aside to %s. Delete it when you no longer want it.", link, superseded)

    temporary = link.with_name(link.name + ".new")
    temporary.unlink(missing_ok=True)
    os.symlink(target, temporary, target_is_directory=True)
    os.replace(temporary, link)
