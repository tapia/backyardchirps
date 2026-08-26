"""
Hold the packaged systemd units to what the packages actually install.

The units used to be templates: install.sh substituted APP_DIR and the data directory into
them, so a wrong path became a wrong path on one machine. They are static files now, which
means every path in them can be checked here, once, against what the packages ship.
"""

from pathlib import Path

import pytest

from backyardchirps.integrations.systemd import MANAGED_UNITS

REPO_ROOT = Path(__file__).resolve().parents[3]
UNITS_DIR = REPO_ROOT / "packaging" / "systemd"

# Directories the packages own, so an ExecStart under one of them is a file that ships.
SHIPPED_PREFIXES = ("/usr/lib/backyardchirps/bin/", "/opt/backyardchirps/venv/bin/")

# Units nothing outside systemd starts, so they are absent from the sudoers policy on
# purpose. fetch-models is pulled in by the recorder and started by postinst.
UNMANAGED_UNITS = {"backyardchirps-fetch-models"}

# The three that run as root. Everything else on a station runs as the service user; these
# install packages, restart units and talk to apt, which are all root's work. The web
# process is granted `start` on each and nothing more.
PRIVILEGED_UNITS = {
    "backyardchirps-update",
    "backyardchirps-rollback",
    "backyardchirps-check-update",
}


def units() -> list[Path]:
    return sorted(UNITS_DIR.glob("*.service"))


def timers() -> list[Path]:
    return sorted(UNITS_DIR.glob("*.timer"))


def directives(unit: Path) -> list[tuple[str, str]]:
    """
    Every Key=Value line in the file, in order, with continuations joined. Order matters
    here, so this keeps it rather than collapsing the file into a dictionary.
    """
    joined: list[tuple[str, str]] = []
    pending = ""
    for raw_line in unit.read_text(encoding="utf-8").splitlines():
        line = pending + raw_line.strip()
        pending = ""
        if not line or line.startswith(("#", "[", ";")):
            continue
        if line.endswith("\\"):
            pending = line[:-1]
            continue
        key, _, value = line.partition("=")
        joined.append((key.strip(), value.strip()))
    return joined


def sections(unit: Path) -> set[str]:
    """
    The section headers, read as headers rather than as text. A unit that explains in a
    comment why it has no [Install] section would otherwise look like it has one.
    """
    return {
        line.strip()
        for line in unit.read_text(encoding="utf-8").splitlines()
        if line.startswith("[") and line.strip().endswith("]")
    }


def value_of(unit: Path, key: str) -> str | None:
    for directive_key, directive_value in directives(unit):
        if directive_key == key:
            return directive_value
    return None


@pytest.mark.parametrize("unit", units(), ids=lambda path: path.name)
def test_every_command_is_a_file_the_packages_ship(unit: Path) -> None:
    commands = [value for key, value in directives(unit) if key in ("ExecStart", "ExecStartPre", "ExecStop")]
    assert commands, f"{unit.name} starts nothing"
    for command in commands:
        assert command.startswith(SHIPPED_PREFIXES), f"{unit.name} runs {command}, which no package installs"


@pytest.mark.parametrize("unit", units(), ids=lambda path: path.name)
def test_the_data_directory_is_set_after_every_environment_file(unit: Path) -> None:
    """
    Load-bearing, and nothing enforced it before. .env lives inside the data directory, so
    it cannot be the file that decides where the data directory is: a stale value in there
    would point a station at an empty tree and it would come up as a fresh install.

    The privileged units read no environment at all. They run a shell script that names
    every path it uses, and anything of theirs that needs Django goes through the manage
    wrapper, which reads the same two files these units would have.
    """
    if unit.stem in PRIVILEGED_UNITS:
        pytest.skip("runs a script that reads no environment")
    keys = [key for key, _ in directives(unit)]
    assert "EnvironmentFile" in keys, f"{unit.name} reads no environment file"
    assert keys.index("Environment") > max(position for position, key in enumerate(keys) if key == "EnvironmentFile"), (
        f"{unit.name} sets BACKYARDCHIRPS_DATA_DIR before an EnvironmentFile that could overwrite it"
    )


@pytest.mark.parametrize("unit", units(), ids=lambda path: path.name)
def test_every_unit_runs_as_the_service_user_unless_it_is_one_of_the_three(unit: Path) -> None:
    """
    Root is the exception and has to stay a short list. Everything that records, serves or
    reads the database runs as the service user, and a unit that quietly moved to root
    would hand the web process more than the policy says it has.
    """
    expected = "root" if unit.stem in PRIVILEGED_UNITS else "backyardchirps"
    assert value_of(unit, "User") == expected


def test_the_recorder_is_in_the_audio_group() -> None:
    """
    Without this the service user cannot open the microphone, and the recorder fails at
    startup with a device error that reads like broken hardware.
    """
    assert value_of(UNITS_DIR / "backyardchirps-recorder.service", "Group") == "audio"


@pytest.mark.parametrize("unit", sorted(PRIVILEGED_UNITS))
def test_the_privileged_units_cannot_be_enabled(unit: str) -> None:
    """
    No [Install] section, so nothing can enable one and each runs only when something
    starts it: the timer for the check, and the web process through sudo for the other two.
    A privileged oneshot that could be enabled is one a boot could run.
    """
    assert "[Install]" not in sections(UNITS_DIR / f"{unit}.service")


def test_the_model_download_is_static() -> None:
    """
    No [Install] section, so nothing can enable it. postinst starts it with --no-block and
    the recorder pulls it in, which is what keeps a Zenodo outage from leaving the package
    unconfigured and apt broken.
    """
    assert "[Install]" not in sections(UNITS_DIR / "backyardchirps-fetch-models.service")


@pytest.mark.parametrize("timer", timers(), ids=lambda path: path.name)
def test_every_timer_has_the_service_it_starts_and_is_enabled(timer: Path) -> None:
    assert (UNITS_DIR / timer.name.replace(".timer", ".service")).exists()
    assert "[Install]" in sections(timer)


def test_the_units_and_the_sudoers_policy_name_the_same_set() -> None:
    """
    Two lists of unit names that have to agree: what the packages install, and what the web
    process is allowed to control. A unit in neither is dead weight; a unit in the policy
    and nowhere else is a grant over something that does not exist.
    """
    packaged = {unit.stem for unit in units()}
    assert packaged - UNMANAGED_UNITS == set(MANAGED_UNITS)
