"""
The options and the phase fixtures for the container install tests.

Each fixture is one state of one machine. They are chained, so asking for a
later one brings up every earlier one in order.

A station installed from packages, which is every station from now on:

  apt_station             a clean machine with the packages installed
  apt_station_with_owner  the same machine, set up
  apt_upgraded            a newer app package installed over it by hand
  apt_self_updated        a third version the station installed itself, the way the button does
  apt_rolled_back         that self-update taken back out again
  apt_removed             the software gone, the recordings kept
  apt_purged              everything gone, data included

The assertions are in test_container_apt.py and the drivers in station.py and apt.py.
"""

import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
from apt import APT_CONTAINER_NAME
from apt import MANAGE
from apt import VENV_PYTHON
from apt import Installed
from apt import Packages
from apt import RolledBack as AptRolledBack
from apt import SelfUpdated as AptSelfUpdated
from apt import Upgraded
from apt import add_source
from apt import build_packages
from apt import install as apt_install
from apt import packages_in
from apt import publish
from apt import purge as apt_purge
from apt import remove as apt_remove
from apt import request_update
from apt import run_rollback
from apt import run_updater
from apt import upgrade as apt_upgrade
from station import CREATE_ADMIN
from station import DATA_DIR
from station import KEPT_CLIP
from station import SERVICE_USER
from station import Station
from station import boot
from station import build_image
from station import remove
from station import require_docker
from station import seed_models


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("station", "the throwaway station these tests install onto")
    group.addoption(
        "--keep-station",
        action="store_true",
        default=False,
        help="leave the container running afterwards, to look around inside it",
    )
    group.addoption(
        "--packages-dir",
        default=None,
        help="install these .deb files instead of building them, for a second run or for CI",
    )


# ---------------------------------------------------------------------------
# The packages, built once and installed on the machines below
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def packages(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Packages:
    already_built = request.config.getoption("--packages-dir")
    if already_built:
        _say(f"installing the packages in {already_built}")
        return packages_in(Path(already_built))
    _say("building the packages: the slow part, since the virtualenv is built in a container")
    return build_packages(tmp_path_factory.mktemp("packages"))


@pytest.fixture(scope="session")
def upgrade_packages(tmp_path_factory: pytest.TempPathFactory) -> Packages:
    """
    A newer app package and nothing else, which is what an ordinary release looks like: the
    code changes, the virtualenv and the species data do not. The version is a PEP 440 local
    version, so it can never collide with a tag and still sorts above the release it came
    from, in dpkg's ordering as well as PEP 440's.

    The suffix is numbered rather than named after what the fixture does. Both orderings
    compare a local version character by character, so `+selfupdate` would sort *below*
    `+upgradetest` and the updater would refuse the second one as older. A number is the one
    way to say "and then this" that both schemes read the same.
    """
    _say("building an app package for the station to upgrade to")
    return build_packages(
        tmp_path_factory.mktemp("upgrade-packages"),
        version_suffix="+test.1",
        only=["backyardchirps"],
    )


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


# ---------------------------------------------------------------------------
# A station installed from packages
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def booted_apt_station(request: pytest.FixtureRequest) -> Iterator[Station]:
    require_docker()
    keep_station = bool(request.config.getoption("--keep-station"))
    build_image()
    _say("booting a clean machine for the package install")
    booted = boot(name=APT_CONTAINER_NAME, python=VENV_PYTHON)
    try:
        yield booted
    finally:
        if keep_station:
            _say(f"still running. Look around with: docker exec -it {APT_CONTAINER_NAME} bash")
        else:
            remove(booted)


@pytest.fixture(scope="session")
def apt_station(booted_apt_station: Station, packages: Packages) -> Installed:
    """
    A clean machine with the packages installed on it, which is where every assertion about
    a packaged station starts.
    """
    seeded = seed_models(booted_apt_station)
    if seeded:
        _say("seeding the acoustic model and GeoModel from the local cache")
    publish(booted_apt_station, packages)
    add_source(booted_apt_station)
    _say(f"installing {packages.app_version} through apt")
    result = apt_install(booted_apt_station)
    _refuse_a_failed_run(booted_apt_station, result, "apt-get install backyardchirps failed")
    return Installed(
        station=booted_apt_station,
        version=packages.app_version,
        output=result.stdout + result.stderr,
    )


@pytest.fixture(scope="session")
def apt_station_with_owner(apt_station: Installed) -> Installed:
    """
    A station somebody has finished setting up: an admin account and no setup token, which
    is what the wizard leaves behind.
    """
    _say("giving the packaged station an owner")
    station = apt_station.station
    created = station.run(["sudo", "-u", SERVICE_USER, MANAGE, "shell", "-c", CREATE_ADMIN])
    if created.returncode != 0:
        raise RuntimeError(f"Could not create an admin account:\n{created.stderr}")
    station.run(["rm", "-f", f"{DATA_DIR}/setup-token"])
    return apt_station


@pytest.fixture(scope="session")
def apt_upgraded(apt_station_with_owner: Installed, upgrade_packages: Packages) -> Upgraded:
    """
    The same machine moved to a newer app package, which is every upgrade a station will
    ever do: dpkg unpacks over the old files and postinst migrates and restarts.
    """
    station = apt_station_with_owner.station
    station.run(["mkdir", "-p", f"{DATA_DIR}/clips"])
    station.run(["touch", KEPT_CLIP])
    station.run(["chown", "-R", f"{SERVICE_USER}:{SERVICE_USER}", f"{DATA_DIR}/clips"])
    database_inode = station.inode_of(f"{DATA_DIR}/detections.db")
    secret_key = station.output_of(["grep", "-h", "SECRET_KEY", f"{DATA_DIR}/.env"])

    publish(station, upgrade_packages)
    _say(f"upgrading to {upgrade_packages.app_version}")
    result = apt_upgrade(station)
    _refuse_a_failed_run(station, result, "apt-get install --only-upgrade failed")
    return Upgraded(
        station=station,
        version=upgrade_packages.app_version,
        output=result.stdout + result.stderr,
        database_inode=database_inode,
        secret_key=secret_key,
    )


@pytest.fixture(scope="session")
def self_update_packages(tmp_path_factory: pytest.TempPathFactory) -> Packages:
    """
    A third app package, so the station has somewhere to update itself to after the upgrade
    it was given by hand. The next number up from upgrade_packages, for the reason written
    down there.
    """
    _say("building an app package for the station to update itself to")
    return build_packages(
        tmp_path_factory.mktemp("self-update-packages"),
        version_suffix="+test.2",
        only=["backyardchirps"],
    )


@pytest.fixture(scope="session")
def apt_self_updated(apt_upgraded: Upgraded, self_update_packages: Packages) -> AptSelfUpdated:
    """
    The station updating itself, which is what the button does.

    Everything above this installs by calling apt directly, which is the documented manual
    path. This is the other one: the request row, the offer read back as root, the packages
    of the running version saved for the way back, the install, and the health check.
    """
    station = apt_upgraded.station
    publish(station, self_update_packages)
    request_update(station, self_update_packages.app_version)

    _say(f"letting the station update itself to {self_update_packages.app_version}")
    result = run_updater(station)
    _refuse_a_failed_run(station, result, "the updater failed")
    return AptSelfUpdated(
        station=station,
        version=self_update_packages.app_version,
        from_version=apt_upgraded.version,
        output=result.stdout + result.stderr,
    )


@pytest.fixture(scope="session")
def apt_rolled_back(apt_self_updated: AptSelfUpdated) -> AptRolledBack:
    """
    The self-update above, taken back out again, on the branch that costs something.

    The packages it installs are the ones the updater really saved, and the backup it
    restores is the one postinst really wrote. Nothing here arranges either.

    One thing is arranged. Every version is built from the same checkout, so they ship
    identical migrations and the database is never actually ahead. The row added below is
    what "the update changed the shape of the database" looks like from the rollback's
    side, and without it the branch that restores anything would never run.
    """
    station = apt_self_updated.station
    _say("rolling the station back out of the update it made")

    station.sql(
        "insert into django_migrations (app, name, applied) "
        "values ('birds_recorder', '0099_only_in_the_newer_release', datetime('now'))"
    )

    result = run_rollback(station)
    _refuse_a_failed_run(station, result, "the rollback failed")
    return AptRolledBack(
        station=station,
        from_version=apt_self_updated.version,
        to_version=apt_self_updated.from_version,
        output=result.stdout + result.stderr,
    )


@pytest.fixture(scope="session")
def apt_removed(apt_rolled_back: AptRolledBack) -> Station:
    """
    The software taken away, the recordings left alone. This is the promise an owner is given
    in the docs, and the half of it that `apt purge` does not keep.
    """
    _say("removing the package")
    station = apt_rolled_back.station
    _refuse_a_failed_run(station, apt_remove(station), "apt-get remove failed")
    return station


@pytest.fixture(scope="session")
def apt_purged(apt_removed: Station) -> Station:
    """
    Everything, data included. Debian policy leaves no room for a purge that keeps
    something, so this is the one step nothing can soften.
    """
    _say("purging every package")
    _refuse_a_failed_run(apt_removed, apt_purge(apt_removed), "apt-get purge failed")
    return apt_removed
