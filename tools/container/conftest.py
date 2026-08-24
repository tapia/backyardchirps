"""
The options and the phase fixtures for the container install tests.

There are two chains, one machine each, and they run side by side while the move from
tarballs to packages is under way. Each fixture is one state of one machine, and they are
chained, so asking for a later one brings up every earlier one in order.

From a release tarball, through install.sh and deploy/apply.sh:

  station             a clean machine with the release installed
  station_with_owner  the same machine, given an admin account and no setup token
  reinstalled         the same version installed over itself, which is how a station updates
  updated             a newer version installed beside it and switched to
  uninstalled         the software removed, the recordings kept

From .deb files, through apt and the maintainer scripts:

  apt_station             a clean machine with the packages installed
  apt_station_with_owner  the same machine, set up
  apt_upgraded            a newer app package installed over it
  apt_removed             the software gone, the recordings kept
  apt_purged              everything gone, data included

The assertions are in test_container_install.py and test_container_apt.py, and the drivers
in station.py and apt.py.
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
from apt import Upgraded
from apt import add_source
from apt import build_packages
from apt import install as apt_install
from apt import packages_in
from apt import publish
from apt import purge as apt_purge
from apt import remove as apt_remove
from apt import upgrade as apt_upgrade
from station import APP_DIR
from station import CONTAINER_NAME
from station import CREATE_ADMIN
from station import DATA_DIR
from station import INSTALL_DIR
from station import KEPT_CLIP
from station import SERVICE_USER
from station import Reinstalled
from station import Release
from station import RolledBack
from station import SelfUpdated
from station import Station
from station import Updated
from station import boot
from station import build_image
from station import build_release
from station import copy_release_in
from station import install
from station import remove
from station import request_and_run_update
from station import require_docker
from station import save_models
from station import seed_models
from station import snapshot
from station import uninstall


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
def booted_station(request: pytest.FixtureRequest) -> Iterator[Station]:
    require_docker()
    keep_station = bool(request.config.getoption("--keep-station"))
    _say("building the image")
    build_image()
    _say("booting a clean station")
    try:
        booted = boot()
        _say(f"systemd is up, failed units: {', '.join(booted.failed_units()) or 'none'}")
        yield booted
    finally:
        if keep_station:
            _say(f"still running. Look around with: docker exec -it {CONTAINER_NAME} bash")
            _say(f"then: docker rm -f {CONTAINER_NAME}")
        else:
            remove(Station(name=CONTAINER_NAME))


@pytest.fixture(scope="session")
def station(booted_station: Station, release: Release) -> Station:
    """
    A clean machine with the release installed on it, which is where every run starts.
    """
    _say("copying the installer and the tarball in")
    copy_release_in(booted_station, release)
    seeded = seed_models(booted_station)
    if seeded:
        _say("seeding the acoustic model and GeoModel from the local cache")
    _say(
        f"installing {release.version}: the slow part, Python packages" + ("" if seeded else " and the model download")
    )
    _refuse_a_failed_run(booted_station, install(booted_station, release), "install.sh failed")

    # Keep what this run fetched, so the next one starts warm. Done after the install rather
    # than at the end, because everything below reinstalls onto this same machine and only
    # the first install can have downloaded anything.
    if not seeded:
        _say("caching the models for the next run")
        save_models(booted_station)
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
def self_update_release(tmp_path_factory: pytest.TempPathFactory) -> Release:
    """
    A third tarball, so the station has somewhere to update itself to after the update it was
    given by hand. Same trick as upgrade_release: a PEP 440 local version, which can never
    collide with a tag.
    """
    _say("staging a tarball for the station to update itself to")
    return build_release(tmp_path_factory.mktemp("selfupdate"), version_suffix="+selfupdate")


@pytest.fixture(scope="session")
def self_updated(updated: Updated, self_update_release: Release) -> SelfUpdated:
    """
    The station updating itself, through deploy/update.sh, which is what the button does.

    Everything above this installs by running install.sh directly, which is the documented
    manual path. This is the other one: the request row, the manifest re-read as root, the
    database backup, install.sh called by the updater, and the health check.
    """
    station = updated.station
    before = snapshot(station)

    _say(f"letting the station update itself to {self_update_release.version}")
    result = request_and_run_update(station, self_update_release)
    _refuse_a_failed_run(station, result, "deploy/update.sh failed")
    return SelfUpdated(
        station=station,
        version=self_update_release.version,
        before=before,
        output=result.stdout + result.stderr,
    )


@pytest.fixture(scope="session")
def rolled_back(self_updated: SelfUpdated) -> RolledBack:
    """
    The self-update above, taken back out again, on the branch that costs something.

    The backup it restores is the one deploy/update.sh really wrote, which is what joins the
    two halves: nothing here arranges it.

    One thing is still arranged. Both releases are built from the same checkout, so they ship
    identical migrations and the database is never actually ahead. The row added below is what
    "the update changed the shape of the database" looks like from rollback.sh's side, and
    without it the branch that restores anything would never run.
    """
    station = self_updated.station
    _say("rolling the station back out of the update it made")

    station.sql(
        "insert into django_migrations (app, name, applied) "
        "values ('birds_recorder', '0099_only_in_the_newer_release', datetime('now'))"
    )

    result = station.run(["bash", f"{APP_DIR}/deploy/rollback.sh"])
    _refuse_a_failed_run(station, result, "rollback.sh failed")
    return RolledBack(
        station=station,
        from_version=self_updated.version,
        to_release=self_updated.before.release,
        output=result.stdout + result.stderr,
    )


@pytest.fixture(scope="session")
def uninstalled(rolled_back: RolledBack) -> Station:
    _say("uninstalling")
    result = uninstall(rolled_back.station)
    _refuse_a_failed_run(rolled_back.station, result, "uninstall.sh failed")
    return rolled_back.station


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
# The package chain
# ---------------------------------------------------------------------------
# A second machine, installed from .deb files through apt rather than from a tarball
# through install.sh. It runs beside the chain above rather than replacing it, so both
# paths stay green while the move from one to the other is under way.


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
    """
    _say("building an app package for the station to upgrade to")
    return build_packages(
        tmp_path_factory.mktemp("upgrade-packages"),
        version_suffix="+upgradetest",
        only=["backyardchirps"],
    )


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
def apt_removed(apt_upgraded: Upgraded) -> Station:
    """
    The software taken away, the recordings left alone. This is `uninstall.sh` without the
    --all, and the promise an owner is given in the docs.
    """
    _say("removing the package")
    station = apt_upgraded.station
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
