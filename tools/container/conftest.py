"""
The options and the phase fixtures for the container install test.

A run walks one machine through four states, and each fixture here is one of them. They are
chained, so asking for a later one brings up every earlier one in order:

  station             a clean machine with the release installed
  station_with_owner  the same machine, given an admin account and no setup token
  reinstalled         the same version installed over itself, which is how a station updates
  updated             a newer version installed beside it and switched to
  uninstalled         the software removed, the recordings kept

The assertions are in test_container_install.py and the driver in station.py.
"""

import subprocess
from collections.abc import Iterator

import pytest
from station import APP_DIR
from station import CONTAINER_NAME
from station import CREATE_ADMIN
from station import DATA_DIR
from station import INSTALL_DIR
from station import KEPT_CLIP
from station import Reinstalled
from station import Release
from station import Station
from station import Updated
from station import boot
from station import build_image
from station import build_release
from station import copy_release_in
from station import install
from station import pick_runtime
from station import remove
from station import snapshot
from station import uninstall


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("station", "the throwaway station these tests install onto")
    group.addoption(
        "--runtime",
        default="",
        help="container runtime: podman or docker. The default prefers podman.",
    )
    group.addoption(
        "--keep-station",
        action="store_true",
        default=False,
        help="leave the container running afterwards, to look around inside it",
    )


@pytest.fixture(scope="session")
def runtime(request: pytest.FixtureRequest) -> str:
    return pick_runtime(str(request.config.getoption("--runtime")))


@pytest.fixture(scope="session")
def release(tmp_path_factory: pytest.TempPathFactory) -> Release:
    _say("staging a release tarball")
    return build_release(tmp_path_factory.mktemp("release"))


@pytest.fixture(scope="session")
def upgrade_release(tmp_path_factory: pytest.TempPathFactory) -> Release:
    """
    The second tarball comes from this same checkout, marked with a PEP 440 local version. That
    is what --version-suffix is for, so no test-only way to change a release's version had to be
    invented: a local version can never equal a tag, and 0.1.2+upgradetest reads as newer than
    0.1.2 under PEP 440.
    """
    _say("staging an upgrade tarball")
    return build_release(tmp_path_factory.mktemp("upgrade"), version_suffix="+upgradetest")


@pytest.fixture(scope="session")
def booted_station(request: pytest.FixtureRequest, runtime: str) -> Iterator[Station]:
    keep_station = bool(request.config.getoption("--keep-station"))
    _say(f"building the image with {runtime}")
    build_image(runtime)
    _say("booting a clean station")
    try:
        booted = boot(runtime)
        _say(f"systemd is up, failed units: {', '.join(booted.failed_units()) or 'none'}")
        yield booted
    finally:
        if keep_station:
            _say(f"still running. Look around with: {runtime} exec -it {CONTAINER_NAME} bash")
            _say(f"then: {runtime} rm -f {CONTAINER_NAME}")
        else:
            remove(Station(runtime=runtime, name=CONTAINER_NAME))


@pytest.fixture(scope="session")
def station(booted_station: Station, release: Release) -> Station:
    """
    A clean machine with the release installed on it, which is where every run starts.
    """
    _say("copying the installer and the tarball in")
    copy_release_in(booted_station, release)
    _say(f"installing {release.version}: the slow part, Python packages and the model download")
    _refuse_a_failed_run(booted_station, install(booted_station, release), "install.sh failed")
    return booted_station


@pytest.fixture(scope="session")
def station_with_owner(station: Station) -> Station:
    """
    A station somebody has finished setting up: it has an admin account and no setup token, which
    is exactly what the wizard leaves behind.
    """
    _say("giving the station an owner")
    created = station.run_as_service_user(
        f"BACKYARDCHIRPS_DATA_DIR={DATA_DIR} {APP_DIR}/.venv/bin/python {APP_DIR}/manage.py shell -c '{CREATE_ADMIN}'"
    )
    if created.returncode != 0:
        raise RuntimeError(f"Could not create an admin account to test the update path with:\n{created.stderr}")

    # What POST /api/setup/complete does once the wizard is finished.
    station.run(["rm", "-f", f"{DATA_DIR}/setup-token"])
    return station


@pytest.fixture(scope="session")
def reinstalled(station_with_owner: Station, release: Release) -> Reinstalled:
    """
    The same version installed over itself.

    Updating is documented as re-running the installer, so this is the ordinary path and not an
    edge case. The failure it guards against is silent and total: setup completion is derived as
    "has an admin and no longer has a token", so an installer that writes a fresh token every
    time flips a configured station back to unconfigured. The router then sends every route to
    the wizard, and the wizard refuses to create a second admin, leaving the owner locked out of
    their own site.
    """
    _say("running the installer again on a station that has an owner")
    result = install(station_with_owner, release)
    _refuse_a_failed_run(station_with_owner, result, "Re-running install.sh on a configured station failed")
    return Reinstalled(station=station_with_owner, output=result.stdout + result.stderr)


@pytest.fixture(scope="session")
def updated(reinstalled: Reinstalled, upgrade_release: Release) -> Updated:
    """
    A newer version installed beside the running one and switched to.

    installation.md tells users to update by re-running the installer, and until the updater
    lands that is the only way anyone gets a new version. Installing the same version over itself
    never moves the symlink and never proves a release can be replaced, so this one installs a
    different version, which is the path a user actually takes.
    """
    station = reinstalled.station
    before = snapshot(station)
    station.run_as_service_user(f"mkdir -p {DATA_DIR}/clips && touch {KEPT_CLIP}")

    _say(f"updating to {upgrade_release.version}")
    station.copy_in(upgrade_release.tarball_path, f"{INSTALL_DIR}/{upgrade_release.tarball_name}")
    result = install(station, upgrade_release)
    _refuse_a_failed_run(station, result, f"Updating to {upgrade_release.version} failed")
    return Updated(station=station, version=upgrade_release.version, before=before)


@pytest.fixture(scope="session")
def uninstalled(updated: Updated) -> Station:
    _say("uninstalling")
    result = uninstall(updated.station)
    _refuse_a_failed_run(updated.station, result, "uninstall.sh failed")
    return updated.station


def _refuse_a_failed_run(station: Station, result: subprocess.CompletedProcess[str], what_failed: str) -> None:
    """
    Every failure points at the install log, and on CI nobody can open a shell to read it, so the
    tail of it comes out in the message instead.
    """
    if result.returncode == 0:
        return
    raise RuntimeError(
        f"{what_failed} (exit {result.returncode}). Re-run with --keep-station and look around.\n"
        f"{result.stdout}\n{result.stderr}\n"
        f"--- last lines of the install log ---\n{station.install_log_tail()}"
    )


def _say(message: str) -> None:
    """
    Progress for a run where a single step can take minutes. Only visible with -s, which is why
    the CI job passes it, and flushed because stdout is block-buffered whenever it is a pipe:
    without this the whole story arrives at the end, which is exactly when it is no longer
    progress.
    """
    print(f"[station] {message}", flush=True)
