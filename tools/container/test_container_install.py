"""
Run install.sh on a clean throwaway machine and check what came out, then update that machine to
a second version and check that too. Both releases are built here and never published, so nothing
has to be tagged first.

  uv run --no-project --with pytest pytest -o addopts="" tools/container -v -s
  uv run --no-project --with pytest pytest -o addopts="" tools/container -v -s --keep-station

Needs docker, and it is slow: it builds two real tarballs, resolves every Python
dependency inside the container and downloads the acoustic model. --no-project keeps it
out of the project environment, which none of this needs, and -o addopts="" drops the coverage
report the project suite asks for.

The point is a machine that has never worked before. Anything that only passes because of state
left behind by an earlier attempt fails here, which is exactly the class of problem an installer
has.

Not covered: audio, and real Pi hardware. A green run says the deploy is sound, not that the
station records. The installer's hardware checks are covered by tests/unit/test_preflight.py.

**Order matters here, which is unusual for a test file.** One machine is walked through five
states, each fixture in conftest.py building on the one before, and a test sees whichever state
its fixture names. The tests are written in that order, so a new one goes next to the others that
share its fixture, never at the end.
"""

import pytest
from station import APP_DIR
from station import DAEMONS
from station import DATA_DIR
from station import INSTALL_ROOT
from station import KEPT_CLIP
from station import SERVICE_USER
from station import TIMED_JOBS
from station import Reinstalled
from station import Station
from station import Updated

# ---------------------------------------------------------------------------
# A clean machine, freshly installed
# ---------------------------------------------------------------------------


def test_the_layout_can_swap_releases(station: Station) -> None:
    assert station.succeeds(["test", "-L", APP_DIR]), (
        f"{APP_DIR} is not a symlink, so an update could not swap releases."
    )

    release_target = station.real_path(APP_DIR)
    assert release_target.startswith(f"{INSTALL_ROOT}/releases/"), (
        f"current points at {release_target}, which is not under {INSTALL_ROOT}/releases."
    )


def test_the_installed_release_carries_a_prebuilt_frontend(station: Station) -> None:
    assert station.path_exists(f"{APP_DIR}/frontend/dist/.prebuilt")


def test_the_service_user_can_reach_a_microphone(station: Station) -> None:
    assert station.succeeds(["id", SERVICE_USER]), f"The {SERVICE_USER} user was not created."
    assert "audio" in station.groups_of(SERVICE_USER), (
        f"{SERVICE_USER} is not in the audio group, so the recorder cannot open a device."
    )


def test_the_service_user_owns_the_data_directory(station: Station) -> None:
    assert station.owner_of(DATA_DIR) == SERVICE_USER


def test_a_usable_secret_key_was_generated(station: Station) -> None:
    """
    The installer generates this rather than asking anyone for it, so a station that reaches this
    point is already usable without a person editing a file.
    """
    secret_key = station.output_of(["grep", "^SECRET_KEY=", f"{DATA_DIR}/.env"]).removeprefix("SECRET_KEY=")
    assert len(secret_key) >= 16


def test_the_environment_file_and_the_token_are_private(station: Station) -> None:
    assert station.mode_of(f"{DATA_DIR}/.env") == "640"
    assert station.mode_of(f"{DATA_DIR}/setup-token") == "600"


def test_the_sudoers_policy_is_valid(station: Station) -> None:
    assert station.succeeds(["visudo", "-cf", "/etc/sudoers.d/backyardchirps"])


def test_the_service_user_may_restart_its_own_recorder(station: Station) -> None:
    """
    The grant the station cannot work without. The recorder reads lat/lon and the confidence
    threshold once at startup, so the wizard has to restart it after those change.
    """
    assert station.sudo_permits("/bin/systemctl restart backyardchirps-recorder")


@pytest.mark.parametrize(
    "command",
    [
        pytest.param("/bin/systemctl restart nginx", id="a-unit-that-is-not-ours"),
        pytest.param("/bin/systemctl restart backyardchirps-recorder nginx", id="ours-and-then-one-that-is-not"),
        pytest.param("/bin/systemctl stop backyardchirps-web ssh", id="ours-and-then-the-way-back-in"),
        pytest.param("/bin/systemctl restart backyardchirps-update", id="a-unit-that-does-not-exist-yet"),
        pytest.param("/bin/systemctl daemon-reload", id="a-verb-the-policy-does-not-grant"),
        pytest.param("/bin/su", id="something-that-is-not-systemctl"),
    ],
)
def test_the_service_user_may_not_reach_past_its_own_units(station: Station, command: str) -> None:
    """
    The policy used to say `backyardchirps-*`, which reads like "our units" and was not.
    sudo matches the arguments as one concatenated string, so the wildcard ran across word
    boundaries: `stop backyardchirps-web ssh` matched it, and so would the root-owned
    updater of Phase 5, from the moment its unit was installed.

    tests/unit/test_sudoers_policy.py checks the policy install.sh renders, which is fast and
    runs anywhere. This checks the one a station is really running, and it is the only place
    sudo itself gets a say in what the policy means.
    """
    assert not station.sudo_permits(command)


@pytest.mark.parametrize("unit", [*DAEMONS, *TIMED_JOBS])
def test_every_unit_runs_as_the_service_user(station: Station, unit: str) -> None:
    """
    Which account a unit runs as is the whole point of the service user, and it is checkable
    whether or not the unit is healthy.
    """
    unit_user = station.unit_property(unit, "User")
    assert unit_user == SERVICE_USER, f"{unit} runs as '{unit_user or 'the default'}' rather than {SERVICE_USER}."


def test_the_web_server_is_running(station: Station) -> None:
    assert station.unit_is_active("backyardchirps-web"), (
        "Re-run with --keep-station, then 'journalctl -u backyardchirps-web'."
    )


def test_the_recorder_waits_for_the_wizard(station: Station) -> None:
    """
    The recorder must NOT be running yet. A station that has not been through the wizard has no
    coordinates, and with none BirdNET matches against every species on earth, so it would fill
    the database with rubbish. apply.sh leaves it enabled but stopped, and the wizard starts it.

    This is also why the container needs no capture device.
    """
    assert station.unit_is_enabled("backyardchirps-recorder"), (
        "backyardchirps-recorder was not enabled, so the wizard could not start it."
    )
    assert not station.unit_is_active("backyardchirps-recorder"), (
        "backyardchirps-recorder is recording on a station nobody has configured yet."
    )


@pytest.mark.parametrize("job", TIMED_JOBS)
def test_the_timers_are_enabled(station: Station, job: str) -> None:
    assert station.unit_is_enabled(f"{job}.timer")


def test_the_database_was_created_and_is_writable_by_the_services(station: Station) -> None:
    """
    The installer runs as root, so the migration must not have left a root-owned database, or the
    recorder would fail on its first detection.
    """
    assert station.path_exists(f"{DATA_DIR}/detections.db"), f"No database was created in {DATA_DIR}."

    owner = station.owner_of(f"{DATA_DIR}/detections.db")
    assert owner == SERVICE_USER, (
        f"detections.db is owned by {owner} rather than {SERVICE_USER}, so the services cannot write to it."
    )

    # Asked of the station rather than counted here. A count of application tables has to be
    # edited every time a model is added, so it fails for the one reason it was never meant to
    # catch, while `migrate --check` exits non-zero for exactly the reason this cares about:
    # something in the release has not been applied to the database the station will use.
    migrated = station.run_as_service_user(
        f"BACKYARDCHIRPS_DATA_DIR={DATA_DIR} {APP_DIR}/.venv/bin/python {APP_DIR}/manage.py migrate --check"
    )
    assert migrated.returncode == 0, f"The database is not fully migrated:\n{migrated.stdout}{migrated.stderr}"


def test_every_message_catalog_is_compiled(station: Station) -> None:
    """
    A release carries the .po a translator edits, and gettext reads only the .mo the deploy
    compiles from it. Without this the wizard's language step would take a choice and every page
    after it would come back English.

    Counted rather than named, so a language added later is covered without anybody remembering
    to come back here.
    """
    catalogs = station.files_matching(f"{APP_DIR}/backyardchirps/locale", "*.po")
    compiled = station.files_matching(f"{APP_DIR}/backyardchirps/locale", "*.mo")

    assert catalogs, "The release carries no message catalogs at all."
    assert len(compiled) == len(catalogs), (
        f"{len(compiled)} of {len(catalogs)} message catalogs were compiled, so the site can only be English."
    )


def test_tensorflow_stays_out_of_a_default_install(station: Station) -> None:
    assert station.path_exists(f"{APP_DIR}/.venv/bin/python"), "No virtualenv was built."
    assert not station.succeeds([f"{APP_DIR}/.venv/bin/python", "-c", "import tensorflow"]), (
        "TensorFlow is installed. The birdnet2 extra should stay out of a default install."
    )


def test_nginx_serves_the_site(station: Station) -> None:
    assert station.http_status("http://localhost/") == "200"


def test_the_api_answers(station: Station) -> None:
    assert station.http_status("http://localhost/api/species/") == "200"


def test_the_setup_wizard_is_reachable_and_asks_for_the_token(station: Station) -> None:
    """
    What a browser asks first. If this is wrong nobody can ever set the station up, which is the
    one failure an install cannot recover from on its own.
    """
    status = station.http_json("http://localhost/api/setup/status/")

    assert status["is_complete"] is False, f"/api/setup/status/ does not report an unconfigured station: {status}"
    assert status["token_required"] is True, (
        f"/api/setup/status/ does not ask for the token the installer just wrote: {status}"
    )


def test_nginx_serves_the_collected_static_files(station: Station) -> None:
    """
    Static files are collected into DATA_DIR and served by nginx, which runs as www-data and owns
    none of it. A 403 here means the data directory is not traversable; a 404 means collectstatic
    wrote somewhere nginx is not looking.
    """
    assert station.http_status("http://localhost/static/admin/css/base.css") == "200"


# ---------------------------------------------------------------------------
# A station somebody has finished setting up
# ---------------------------------------------------------------------------


def test_a_station_with_an_owner_reports_setup_complete(station_with_owner: Station) -> None:
    status = station_with_owner.http_json("http://localhost/api/setup/status/")
    assert status["is_complete"] is True, (
        f"The station does not report itself configured after being given an owner: {status}"
    )


# ---------------------------------------------------------------------------
# The installer run again on that station, which is how updating is documented
# ---------------------------------------------------------------------------


def test_no_token_is_written_onto_a_station_that_has_an_owner(reinstalled: Reinstalled) -> None:
    assert not reinstalled.station.path_exists(f"{DATA_DIR}/setup-token"), (
        "The installer wrote a setup token onto a station that already has an owner, which locks "
        "that owner out of the site."
    )


def test_no_token_is_offered_to_a_station_that_has_an_owner(reinstalled: Reinstalled) -> None:
    assert "Setup token:" not in reinstalled.output


def test_a_reinstall_leaves_the_station_configured(reinstalled: Reinstalled) -> None:
    status = reinstalled.station.http_json("http://localhost/api/setup/status/")
    assert status["is_complete"] is True, f"The station lost its setup state when the installer ran again: {status}"


# ---------------------------------------------------------------------------
# A newer version installed over it
# ---------------------------------------------------------------------------


def test_the_update_went_live(updated: Updated) -> None:
    release_after = updated.station.real_path(APP_DIR)

    assert release_after != updated.before.release, (
        f"{APP_DIR} still points at {updated.before.release}, so the update never went live."
    )
    assert release_after.endswith(f"/releases/{updated.version}"), (
        f"current points at {release_after} rather than the release named {updated.version}."
    )


def test_the_running_release_reports_the_new_version(updated: Updated) -> None:
    """
    The version the site reports comes from the package metadata that uv sync writes, not from the
    directory name, so read it the way Django does. Through the symlink on purpose: that is the
    path every unit starts from.
    """
    read_version = 'import importlib.metadata; print(importlib.metadata.version("backyardchirps"))'
    installed_version = updated.station.run_as_service_user(
        f"{APP_DIR}/.venv/bin/python -c '{read_version}'"
    ).stdout.strip()

    assert installed_version == updated.version, (
        f"The station reports version {installed_version} rather than {updated.version}, so the "
        "site would name the wrong one."
    )


def test_the_previous_release_is_still_on_disk(updated: Updated) -> None:
    """
    Rolling back needs somewhere to roll back to, and the installer keeps three.
    """
    assert updated.station.path_exists(updated.before.release)


def test_the_secret_key_survived_the_update(updated: Updated) -> None:
    secret_key_after = updated.station.output_of(["grep", "^SECRET_KEY=", f"{DATA_DIR}/.env"])
    assert secret_key_after == updated.before.secret_key, (
        "The update generated a new SECRET_KEY, which signs out every session and invalidates "
        "every password reset link."
    )


def test_the_database_was_migrated_in_place(updated: Updated) -> None:
    inode_after = updated.station.inode_of(f"{DATA_DIR}/detections.db")
    assert inode_after == updated.before.database_inode, (
        "detections.db was replaced rather than migrated in place, so the station lost its detections."
    )


def test_the_recordings_survived_the_update(updated: Updated) -> None:
    assert updated.station.path_exists(KEPT_CLIP), f"The update deleted a recording out of {DATA_DIR}/clips."


def test_an_update_does_not_throw_the_station_back_into_the_wizard(updated: Updated) -> None:
    status = updated.station.http_json("http://localhost/api/setup/status/")
    assert status["is_complete"] is True, f"The station was thrown back into the wizard by an update: {status}"


def test_the_updated_station_still_serves_the_site_and_the_api(updated: Updated) -> None:
    assert updated.station.http_status("http://localhost/") == "200"
    assert updated.station.http_status("http://localhost/api/species/") == "200"


def test_a_failed_build_leaves_the_running_release_alone(updated: Updated) -> None:
    """
    The expensive half of a deploy happens before anything is switched over, so a build that dies
    has to leave the station exactly as it found it: still pointed at the release that works, and
    still able to survive a reboot. Getting this backwards is silent, which is what makes it worth
    a test: the station carries on serving from files it already has open, and only dies the next
    time anything restarts it.

    A release directory holding nothing but deploy/ is the cheapest way to fail. It gets as far as
    `uv sync`, which is where a real deploy is most likely to break, and that is above the swap.
    """
    station = updated.station
    broken_release = f"{INSTALL_ROOT}/releases/9.9.9-broken"
    live_release_before = station.real_path(APP_DIR)

    station.run(["mkdir", "-p", broken_release])
    station.run(["cp", "-r", f"{live_release_before}/deploy", f"{broken_release}/deploy"])
    try:
        applied = station.run(
            [
                "env",
                f"BACKYARDCHIRPS_APP_DIR={broken_release}",
                f"BACKYARDCHIRPS_LINK_DIR={APP_DIR}",
                f"BACKYARDCHIRPS_DATA_DIR={DATA_DIR}",
                f"BACKYARDCHIRPS_SERVICE_USER={SERVICE_USER}",
                "bash",
                f"{broken_release}/deploy/apply.sh",
            ]
        )
        assert applied.returncode != 0, "apply.sh reported success on a release with no code in it."

        live_release_after = station.real_path(APP_DIR)
        assert live_release_after == live_release_before, (
            f"A failed build moved {APP_DIR} from {live_release_before} to {live_release_after}, "
            "so the next restart would start a release that was never built."
        )
        assert station.unit_is_active("backyardchirps-web"), "A failed build took the web server down with it."
    finally:
        station.run(["rm", "-rf", broken_release])


# ---------------------------------------------------------------------------
# Taking it apart again
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        INSTALL_ROOT,
        "/etc/systemd/system/backyardchirps-web.service",
        "/etc/nginx/sites-enabled/backyardchirps",
    ],
)
def test_the_software_is_gone(uninstalled: Station, path: str) -> None:
    assert not uninstalled.path_exists(path), f"{path} survived the uninstall."


def test_the_web_server_is_stopped(uninstalled: Station) -> None:
    assert not uninstalled.unit_is_active("backyardchirps-web")


def test_the_recordings_are_kept(uninstalled: Station) -> None:
    """
    Run without --all, so the uninstall has to remove the software and keep every recording. A
    station being taken apart must not take the data with it by accident.
    """
    assert uninstalled.path_exists(f"{DATA_DIR}/detections.db"), (
        "The uninstall deleted the database, and it was not asked to."
    )
