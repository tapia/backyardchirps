"""
Install a station from packages on a clean machine and check what came out.

What is under test is dpkg plus four maintainer scripts, which is what replaced a thousand
lines of installer. Two machines, from the same image: one walked from a clean install to a
purge, and one that had a tarball station on it before the packages arrived.

Order matters here. The fixtures are chained and session-scoped, so a machine is installed
once and walked forward: install, owner, upgrade, self-update, rollback, remove, purge. The
last two take the station apart, so every assertion about a working one has to come before
them.

Run it with:

    uv run --no-project --with pytest pytest tools/container -v -s

Needs docker, and an arm64 machine for the packages to be installable at all.
"""

from apt import CODE_DIR
from apt import MANAGE
from apt import PACKAGE_DIR
from apt import RENAME_LEFTOVERS
from apt import SCOPED_UPDATE
from apt import SHARE_DIR
from apt import TARBALL_LEFTOVERS
from apt import VENV_PYTHON
from apt import Installed
from apt import RolledBack
from apt import SelfUpdated
from apt import TakenOver
from apt import Upgraded
from apt import available_update
from apt import control_field
from apt import http_status
from apt import installed_version
from apt import old_units_in_etc
from apt import run_check
from apt import update_status
from station import DATA_DIR
from station import KEPT_CLIP
from station import SERVICE_USER
from station import Station

DAEMONS = ("backyardchirps-web", "backyardchirps-recorder")
TIMERS = (
    "backyardchirps-update-species.timer",
    "backyardchirps-clip-disk-quota.timer",
    "backyardchirps-check-update.timer",
)


# ---------------------------------------------------------------------------
# What apt put on the machine
# ---------------------------------------------------------------------------


def test_apt_installs_all_three_packages(apt_station: Installed) -> None:
    """
    One package name was asked for. The other two came from Depends:, which is the whole
    point of the split: a code release does not carry a virtualenv.
    """
    for package in ("backyardchirps", "backyardchirps-deps", "backyardchirps-species-data"):
        assert installed_version(apt_station.station, package), f"{package} is not installed"


def test_the_version_the_site_reports_is_the_version_apt_installed(apt_station: Installed) -> None:
    """
    Two version strings that have to be the same one: dpkg's, and the one importlib.metadata
    reads out of the dist-info beside the code. The site shows the second and the updater
    compares the first.
    """
    reported = apt_station.station.output_of(
        ["sudo", "-u", SERVICE_USER, MANAGE, "shell", "-c", "from django.conf import settings; print(settings.VERSION)"]
    ).splitlines()[-1]

    assert reported == apt_station.version
    assert installed_version(apt_station.station) == apt_station.version


def test_the_code_is_importable_from_the_virtualenv(apt_station: Installed) -> None:
    """
    The code lives outside the virtualenv, and a single .pth file in its site-packages is
    what joins the two. Without it every unit dies at startup on an import error.
    """
    assert apt_station.station.succeeds([VENV_PYTHON, "-c", "import backyardchirps; print(backyardchirps.__file__)"])
    assert apt_station.station.path_exists(f"{CODE_DIR}/backyardchirps.dist-info/METADATA")


def test_nothing_was_compiled_on_the_station(apt_station: Installed) -> None:
    """
    The reason for all of this. The virtualenv arrives built, so a station needs no
    compiler, no uv and no network to install one.
    """
    assert not apt_station.station.succeeds(["command", "-v", "uv"])
    assert not apt_station.station.succeeds(["command", "-v", "gcc"])


def test_the_species_data_is_the_full_taxonomy(apt_station: Installed) -> None:
    """
    The repository tracks a sample of a few hundred species. A station has to get the whole
    thing, or the recorder drops every detection it cannot name.
    """
    counted = apt_station.station.output_of(
        [
            VENV_PYTHON,
            "-c",
            "import json;print(len(json.load(open('/usr/share/backyardchirps/species-data/taxonomy/"
            "birdnet_taxonomy.json'))))",
        ]
    )
    assert int(counted) > 10_000


def test_the_static_files_were_collected_by_the_build(apt_station: Installed) -> None:
    """
    collectstatic runs where the package is built, so nothing on the station has to run it
    and dpkg can remove what a later version stops shipping.
    """
    assert apt_station.station.path_exists(f"{SHARE_DIR}/staticfiles/admin")
    assert apt_station.station.path_exists(f"{SHARE_DIR}/frontend/index.html")


def test_the_message_catalogs_are_compiled(apt_station: Installed) -> None:
    """
    gettext is not installed on a station any more, so the .mo files have to come in the
    package. Without them the site is English whatever anybody chose.
    """
    assert apt_station.station.files_matching(CODE_DIR, "django.mo")


# ---------------------------------------------------------------------------
# What postinst decided
# ---------------------------------------------------------------------------


def test_the_service_user_exists_and_owns_its_data(apt_station: Installed) -> None:
    station = apt_station.station
    assert station.owner_of(DATA_DIR) == SERVICE_USER
    assert station.owner_of(f"{DATA_DIR}/detections.db") == SERVICE_USER


def test_the_update_directory_belongs_to_root(apt_station: Installed) -> None:
    """
    The trust boundary, unchanged from the tarball path. The status file sits in a directory
    the web process cannot write, so it cannot replace it with a symlink and have root follow
    that on the next update.
    """
    assert apt_station.station.owner_of(f"{DATA_DIR}/update") == "root"


def test_the_environment_file_is_written_and_private(apt_station: Installed) -> None:
    station = apt_station.station
    assert station.mode_of(f"{DATA_DIR}/.env") == "640"
    assert "SECRET_KEY=" in station.read(f"{DATA_DIR}/.env")


def test_a_new_station_gets_a_setup_token(apt_station: Installed) -> None:
    """
    Written before the slow steps, so its absence has one meaning: setup is finished. A
    station with no token and no admin is one anyone on the network can claim.
    """
    station = apt_station.station
    assert station.path_exists(f"{DATA_DIR}/setup-token")
    assert station.mode_of(f"{DATA_DIR}/setup-token") == "600"


def test_the_migrations_ran(apt_station: Installed) -> None:
    assert apt_station.station.succeeds(["sudo", "-u", SERVICE_USER, MANAGE, "migrate", "--check"])


def test_the_web_service_is_running(apt_station: Installed) -> None:
    assert apt_station.station.unit_is_active("backyardchirps-web")
    assert apt_station.station.unit_is_enabled("backyardchirps-web")


def test_the_recorder_waits_for_the_wizard(apt_station: Installed) -> None:
    """
    A station with no coordinates matches against every species on earth, so recording
    before the wizard finishes fills the database with rubbish. Enabled for the next boot,
    but not started now.
    """
    assert apt_station.station.unit_is_enabled("backyardchirps-recorder")
    assert not apt_station.station.unit_is_active("backyardchirps-recorder")


def test_the_timers_are_running(apt_station: Installed) -> None:
    for timer in TIMERS:
        assert apt_station.station.unit_is_active(timer), f"{timer} is not running"


def test_the_model_download_is_a_unit_rather_than_part_of_the_install(apt_station: Installed) -> None:
    """
    A Zenodo outage used to fail the install. As a unit started with --no-block, it fails in
    the journal instead, and the recorder retries it until the model arrives.
    """
    station = apt_station.station
    assert station.path_exists("/usr/lib/systemd/system/backyardchirps-fetch-models.service")
    assert station.unit_property("backyardchirps-fetch-models.service", "LoadState") == "loaded"


def test_the_sudoers_policy_is_valid_and_narrow(apt_station: Installed) -> None:
    station = apt_station.station
    assert station.succeeds(["visudo", "-cf", "/etc/sudoers.d/backyardchirps"])
    assert station.mode_of("/etc/sudoers.d/backyardchirps") == "440"
    assert station.sudo_permits("/bin/systemctl restart backyardchirps-recorder")
    assert not station.sudo_permits("/bin/systemctl restart nginx")

    # The updater, asked of sudo exactly as the web process runs it. sudo matches a whole
    # argument list, so --no-block is part of the command rather than decoration: the plain
    # form is not granted, and neither is anything that could stop an update half way.
    assert station.sudo_permits("/bin/systemctl start --no-block backyardchirps-update")
    assert not station.sudo_permits("/bin/systemctl start backyardchirps-update")
    assert not station.sudo_permits("/bin/systemctl stop backyardchirps-update")


def test_the_site_answers(apt_station: Installed) -> None:
    station = apt_station.station
    assert http_status(station, "http://localhost/") == "200"
    assert http_status(station, "http://localhost/api/detections/") in ("200", "403")


def test_the_default_nginx_site_is_gone(apt_station: Installed) -> None:
    """
    Debian's default site claims the same port with an exact server_name, and an exact name
    beats a default_server, so leaving it enabled serves a browser the wrong document root.
    """
    assert not apt_station.station.path_exists("/etc/nginx/sites-enabled/default")


def test_the_units_carry_no_placeholders(apt_station: Installed) -> None:
    """
    The units used to be templates the installer substituted paths into. They are static
    files now, so anything that still looks like a placeholder is a path nothing filled in.
    """
    unit = apt_station.station.read("/usr/lib/systemd/system/backyardchirps-web.service")
    assert "APP_DIR" not in unit
    assert "__DATA_DIR__" not in unit


def test_the_release_metadata_the_updater_reads_is_there(apt_station: Installed) -> None:
    """
    Released and Changelog-Url were two keys of manifest.json. They are control fields now,
    which is what lets the manifest go away without the site losing what it shows.
    """
    assert control_field(apt_station.station, "Released")
    assert control_field(apt_station.station, "Changelog-Url").startswith("https://")


# ---------------------------------------------------------------------------
# Upgrading
# ---------------------------------------------------------------------------


def test_the_upgrade_moved_the_version(apt_upgraded: Upgraded) -> None:
    assert installed_version(apt_upgraded.station) == apt_upgraded.version
    reported = apt_upgraded.station.output_of(
        ["sudo", "-u", SERVICE_USER, MANAGE, "shell", "-c", "from django.conf import settings; print(settings.VERSION)"]
    ).splitlines()[-1]
    assert reported == apt_upgraded.version


def test_the_upgrade_kept_the_database_and_the_recordings(apt_upgraded: Upgraded) -> None:
    """
    The one thing an update may never do. Same inode, so the file was not replaced or
    restored from anywhere: it was left alone.
    """
    station = apt_upgraded.station
    assert station.inode_of(f"{DATA_DIR}/detections.db") == apt_upgraded.database_inode
    assert station.path_exists(KEPT_CLIP)


def test_the_upgrade_kept_the_secret_key(apt_upgraded: Upgraded) -> None:
    """
    A new key would log every session out and invalidate every signed value the station has
    handed out. .env is written once and never again.
    """
    assert apt_upgraded.station.output_of(["grep", "-h", "SECRET_KEY", f"{DATA_DIR}/.env"]) == apt_upgraded.secret_key


def test_the_upgrade_backed_the_database_up(apt_upgraded: Upgraded) -> None:
    """
    Taken before the migrations, which are the part of an upgrade that cannot be undone by
    installing the old version again. An owner running `apt upgrade` by hand gets it too,
    which was never true of the tarball path.
    """
    backups = apt_upgraded.station.files_matching(f"{DATA_DIR}/backups", "detections-before-*.db")
    assert backups, "the upgrade left no database backup"


def test_the_upgrade_did_not_hand_the_station_to_somebody_else(apt_upgraded: Upgraded) -> None:
    """
    Completion is "has an admin and no longer has a token", so a token written during an
    upgrade would flip a configured station back to unconfigured and send its owner to a
    wizard that refuses to create a second account.
    """
    assert not apt_upgraded.station.path_exists(f"{DATA_DIR}/setup-token")


def test_the_upgrade_left_the_services_running(apt_upgraded: Upgraded) -> None:
    assert apt_upgraded.station.unit_is_active("backyardchirps-web")
    assert http_status(apt_upgraded.station, "http://localhost/") == "200"


def test_the_update_check_reads_only_our_own_source(apt_upgraded: Upgraded) -> None:
    """
    The flags the daily check will use, proved rather than written down.

    A second source is added first, unsigned, which is what a third-party source looks like
    once its key expires. A plain `apt-get update` then fails outright, and that failure is
    the one a station would report as "update check failed" while having nothing to do with
    us. The scoped call does not see it.

    An unreachable source is not the case to test with: apt only warns about one and still
    exits 0. Losing trust in a source is what it treats as an error.
    """
    station = apt_upgraded.station
    station.run(["cp", "-r", PACKAGE_DIR, "/srv/somebody-elses"])
    station.run(
        [
            "bash",
            "-c",
            "printf 'Types: deb\\nURIs: file:/srv/somebody-elses\\nSuites: ./\\n' "
            "> /etc/apt/sources.list.d/somebody-elses.sources",
        ]
    )
    try:
        plain = station.run(["apt-get", "update"])
        assert plain.returncode != 0, "an unsigned source no longer fails a plain update"

        scoped = station.run(SCOPED_UPDATE)
        assert scoped.returncode == 0
        assert "somebody-elses" not in scoped.stdout + scoped.stderr

        # List-Cleanup=0 is the other half: a scoped run must not throw away the index
        # files belonging to the sources it was told to ignore.
        assert "deb.debian.org" in station.output_of(["ls", "/var/lib/apt/lists"])
    finally:
        station.run(["rm", "-rf", "/srv/somebody-elses", "/etc/apt/sources.list.d/somebody-elses.sources"])


# ---------------------------------------------------------------------------
# Checking for an update
# ---------------------------------------------------------------------------


def test_the_check_stores_what_apt_offers(apt_upgraded: Upgraded) -> None:
    """
    The whole path in one go: the script asks apt, writes its answer down, and hands it to
    the application. A station on the newest version there is has to come out of that
    saying so rather than saying nothing.
    """
    station = apt_upgraded.station
    assert run_check(station).returncode == 0

    stored = available_update(station)
    assert stored["error"] == ""
    assert stored["version"] == apt_upgraded.version
    assert stored["update_available"] is False


def test_the_answer_is_written_where_the_web_process_can_read_it_and_not_write_it(apt_upgraded: Upgraded) -> None:
    """
    The same trust boundary the progress file has. The web process runs as the service user
    and must not be able to put an answer here for the rest of the station to believe.
    """
    station = apt_upgraded.station
    result_file = f"{DATA_DIR}/update/available.json"

    assert station.owner_of(result_file) == "root"
    assert station.owner_of(f"{DATA_DIR}/update") == "root"
    assert station.mode_of(result_file) == "644"


# ---------------------------------------------------------------------------
# Updating itself
# ---------------------------------------------------------------------------


def test_the_station_installed_the_version_it_was_asked_for(apt_self_updated: SelfUpdated) -> None:
    assert installed_version(apt_self_updated.station) == apt_self_updated.version
    assert update_status(apt_self_updated.station)["state"] == "succeeded"


def test_the_self_update_finished_the_script_it_replaced(apt_self_updated: SelfUpdated) -> None:
    """
    The updater is a file belonging to the package it is upgrading. dpkg renames the new
    file over the path rather than writing through it, so the running bash keeps its open
    inode and reaches the end. A maintainer script that stopped the update unit would break
    that, and the run would stop somewhere in the middle with the status file still saying
    "running".
    """
    status = update_status(apt_self_updated.station)

    assert status["step"] == "finished"
    assert status["version"] == apt_self_updated.version


def test_the_self_update_saved_the_packages_to_go_back_to(apt_self_updated: SelfUpdated) -> None:
    """
    This is what replaces keeping three whole releases on disk. Saved before the install,
    so going back needs no network, which is the one moment a station may not have any.
    """
    station = apt_self_updated.station
    saved = station.files_matching(f"{DATA_DIR}/update/rollback", "*.deb")

    assert saved, "the updater saved nothing to go back to"
    versions = station.read(f"{DATA_DIR}/update/rollback/versions")
    assert f"backyardchirps={apt_self_updated.from_version}" in versions


def test_the_self_update_stopped_offering_the_version_it_just_installed(apt_self_updated: SelfUpdated) -> None:
    """
    The badge would otherwise stay up until the timer next ran, which is the next morning,
    on a station that is already up to date.
    """
    stored = available_update(apt_self_updated.station)

    assert stored["version"] == apt_self_updated.version
    assert stored["update_available"] is False


def test_the_self_update_kept_the_recordings(apt_self_updated: SelfUpdated) -> None:
    assert apt_self_updated.station.path_exists(KEPT_CLIP)


# ---------------------------------------------------------------------------
# Going back
# ---------------------------------------------------------------------------


def test_the_rollback_installed_the_version_that_was_running_before(apt_rolled_back: RolledBack) -> None:
    assert installed_version(apt_rolled_back.station) == apt_rolled_back.to_version
    assert update_status(apt_rolled_back.station)["state"] == "succeeded"


def test_the_rollback_restored_the_database_the_update_had_moved_past(apt_rolled_back: RolledBack) -> None:
    """
    The branch that costs something. The database was made to look ahead of the restored
    code, so the rollback had to put back the copy postinst took before the migrations, and
    keep what it replaced rather than deleting it.
    """
    station = apt_rolled_back.station

    assert "restoring" in apt_rolled_back.output or "Restored" in apt_rolled_back.output
    assert station.files_matching(f"{DATA_DIR}/backups", "detections-rolled-back-*.db"), (
        "the database it replaced was thrown away rather than kept"
    )


def test_the_station_answers_again_after_going_back(apt_rolled_back: RolledBack) -> None:
    assert apt_rolled_back.station.unit_is_active("backyardchirps-web")
    assert http_status(apt_rolled_back.station, "http://localhost/") == "200"


def test_going_back_offers_the_version_it_left(apt_rolled_back: RolledBack) -> None:
    """
    A station that rolled back is behind again, and saying so is the difference between one
    an owner can move forward from and one that looks stuck.
    """
    stored = available_update(apt_rolled_back.station)

    assert stored["version"] == apt_rolled_back.from_version
    assert stored["update_available"] is True


# ---------------------------------------------------------------------------
# Taking it away
# ---------------------------------------------------------------------------


def test_remove_stops_and_disables_everything(apt_removed: Station) -> None:
    for unit in DAEMONS:
        assert not apt_removed.unit_is_active(unit), f"{unit} is still running"
    for timer in TIMERS:
        assert not apt_removed.unit_is_active(timer), f"{timer} is still running"


def test_remove_takes_the_code_but_leaves_the_recordings(apt_removed: Station) -> None:
    """
    The promise `apt remove` makes, and the reason purge is a separate word.
    """
    assert not apt_removed.path_exists(f"{CODE_DIR}/backyardchirps")
    assert apt_removed.path_exists(KEPT_CLIP)
    assert apt_removed.path_exists(f"{DATA_DIR}/detections.db")


def test_remove_unhooks_the_nginx_site(apt_removed: Station) -> None:
    assert not apt_removed.path_exists("/etc/nginx/sites-enabled/backyardchirps")


def test_remove_leaves_no_unit_files_behind(apt_removed: Station) -> None:
    """
    The failure the tarball uninstaller kept having: a list of units maintained by hand,
    which stopped two timers when three were shipped. dpkg cannot forget, because it
    recorded every file it installed.
    """
    assert not apt_removed.files_matching("/usr/lib/systemd/system", "backyardchirps-*")


def test_purge_deletes_the_data_and_the_account(apt_purged: Station) -> None:
    """
    Debian policy leaves no room for a purge that keeps something, so this is the one step
    an owner cannot soften. It is why the docs make remove and purge two different words.
    """
    assert not apt_purged.path_exists(DATA_DIR)
    assert not apt_purged.succeeds(["id", SERVICE_USER])
    assert not apt_purged.succeeds(["getent", "group", SERVICE_USER])


def test_purge_leaves_nothing_of_the_station_behind(apt_purged: Station) -> None:
    for path in (
        "/etc/sudoers.d/backyardchirps",
        "/etc/default/backyardchirps",
        "/etc/nginx/sites-available/backyardchirps",
        "/opt/backyardchirps",
        CODE_DIR,
        SHARE_DIR,
    ):
        assert not apt_purged.path_exists(path), f"{path} survived the purge"


# ---------------------------------------------------------------------------
# Taking over a station that was already there
# ---------------------------------------------------------------------------
# Its own machine, and the only place this is exercised. It happens once per station in the
# field, it cannot be tried a second time, and it is the one path that could cost somebody
# every recording they have.


def test_the_takeover_kept_the_database_and_the_recordings(taken_over: TakenOver) -> None:
    """
    The whole promise, in one number. The same inode means the same file: not a copy, not a
    restore from a backup, not a new database beside the old one.
    """
    station = taken_over.station

    assert station.inode_of(f"{DATA_DIR}/detections.db") == taken_over.database_inode
    assert station.path_exists(KEPT_CLIP)


def test_the_takeover_removed_the_units_that_would_shadow_the_packaged_ones(taken_over: TakenOver) -> None:
    """
    The one mistake that cannot be recovered from without a person and a shell. systemd
    searches /etc/systemd/system before /usr/lib, so a unit left there wins for ever and goes
    on pointing at a directory the packages never write to. The machine would look installed,
    run the old code, and nothing anywhere would say so.

    Dangling symlinks count. Disabling a unit whose file is already gone does not remove the
    .wants link that refers to it.
    """
    assert old_units_in_etc(taken_over.station) == []


def test_the_packaged_units_are_the_ones_that_run(taken_over: TakenOver) -> None:
    station = taken_over.station

    assert station.unit_property("backyardchirps-web", "FragmentPath") == (
        "/usr/lib/systemd/system/backyardchirps-web.service"
    )
    assert station.unit_is_active("backyardchirps-web")
    assert http_status(station, "http://localhost/") == "200"


def test_the_takeover_moved_the_old_config_files_aside_rather_than_deleting_them(taken_over: TakenOver) -> None:
    """
    Moved, not deleted. One of them records where a station kept its data, and an owner who
    installed with a data directory of their own needs to be able to read it afterwards.
    """
    station = taken_over.station

    for leftover in TARBALL_LEFTOVERS:
        kept = f"/var/backups/{leftover.rsplit('/', 1)[1]}.tarball-station"
        if leftover.endswith("sudoers.d/backyardchirps"):
            kept = "/var/backups/sudoers-backyardchirps.tarball-station"
        assert station.path_exists(kept), f"{leftover} was not kept aside"


def test_the_takeover_removed_the_files_left_by_the_rename(taken_over: TakenOver) -> None:
    """
    Two files from before the project changed its name, which no installer has ever removed
    because both predate the name it has now. The nginx one takes every request on the
    machine; the sudoers one grants rights over units that no longer exist.
    """
    for leftover in RENAME_LEFTOVERS:
        assert not taken_over.station.path_exists(leftover), f"{leftover} is still there"


def test_the_takeover_removed_the_old_releases_once_the_station_answered(taken_over: TakenOver) -> None:
    """
    Gated on the new station being up, so a takeover that failed leaves the old tree for a
    person to fall back to. It is up, so this is the branch that clears it.
    """
    station = taken_over.station

    assert not station.path_exists("/opt/backyardchirps/releases")
    assert not station.path_exists("/opt/backyardchirps/current")
    # The virtualenv the packages own lives under the same directory and is not the old
    # station's to remove.
    assert station.path_exists("/opt/backyardchirps/venv/bin/python")


def test_the_takeover_removed_the_static_files_nothing_reads_any_more(taken_over: TakenOver) -> None:
    """
    collectstatic used to write into the data directory. The packages ship those files
    instead, so what is left there is read by nothing.
    """
    assert not taken_over.station.path_exists(f"{DATA_DIR}/staticfiles")


def test_the_sudoers_policy_after_a_takeover_is_the_packaged_one(taken_over: TakenOver) -> None:
    """
    The old policy was moved aside and the packaged one installed in its place. A policy that
    does not parse would stop sudo reading the whole of /etc/sudoers.d, so this being valid
    matters more here than anywhere else.
    """
    station = taken_over.station

    assert station.succeeds(["visudo", "-cf", "/etc/sudoers.d/backyardchirps"])
    assert station.sudo_permits("/bin/systemctl restart backyardchirps-recorder")


def test_the_takeover_left_an_owners_drop_in_alone(taken_over: TakenOver) -> None:
    """
    The one thing under /etc/systemd/system that must survive. A drop-in is how an owner is
    told to change a packaged unit, it augments rather than shadows, and a sweep that took
    directories with the files would throw away the only local change the design allows.
    """
    station = taken_over.station
    drop_in = "/etc/systemd/system/backyardchirps-web.service.d/local.conf"

    assert station.path_exists(drop_in)
    assert "SOMETHING_AN_OWNER_SET" in station.unit_property("backyardchirps-web", "Environment")


def test_the_takeover_backed_the_database_up_before_migrating_it(taken_over: TakenOver) -> None:
    """
    The case that is easiest to miss, because a takeover is a first install as far as dpkg is
    concerned and the backup used to be keyed on being an upgrade. A station being taken over
    is many versions behind, so it meets more migrations at once than any ordinary upgrade,
    and it is somebody's real database rather than a fresh one.
    """
    backups = taken_over.station.files_matching(f"{DATA_DIR}/backups", "detections-before-*.db")

    assert backups, "the takeover migrated an existing database without copying it first"
