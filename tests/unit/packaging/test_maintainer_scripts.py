"""
Hold the maintainer scripts to the units the packages actually ship, and away from the one
unit they must never touch.

dpkg runs these four scripts as root in the middle of an install, and a mistake in one
lands on a station rather than on a pull request. Two things are worth pinning. A unit
named in a script and shipped by nothing is a line that silently does nothing; a unit
shipped and named in no script is one that is never enabled or never cleaned up. And
stopping the updater from inside the update it is running would kill it halfway.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "packaging" / "scripts"
UNITS_DIR = REPO_ROOT / "packaging" / "systemd"

# The unit each script is running inside when a station updates itself. Stopping it there
# is the one mistake that cannot be recovered from on the station: the script is killed
# between unpack and configure, and an owner is left with a half-installed package.
#
# postrm is not here. By the time it runs the package is gone and so is the update.
SCRIPTS_THAT_RUN_DURING_AN_UPDATE = ("preinst", "postinst", "prerm")
NEVER_TOUCHED = ("backyardchirps-update.service", "backyardchirps-rollback.service")

UNIT_NAME = re.compile(r"backyardchirps-[a-z-]+\.(?:service|timer)")


def code_of(script: str) -> str:
    """
    The script with its comments taken out, so a unit named in an explanation does not read
    as a unit the script acts on.
    """
    lines = (SCRIPTS_DIR / script).read_text(encoding="utf-8").splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("#"))


def shipped_units() -> set[str]:
    return {path.name for path in UNITS_DIR.iterdir()}


@pytest.mark.parametrize("script", list(SCRIPTS_THAT_RUN_DURING_AN_UPDATE))
def test_nothing_that_runs_during_an_update_names_the_unit_running_it(script: str) -> None:
    for unit in NEVER_TOUCHED:
        assert unit not in code_of(script), f"{script} names {unit}, which is the unit an update runs inside"


@pytest.mark.parametrize("script", ["preinst", "postinst", "prerm", "postrm"])
def test_every_unit_a_script_names_is_one_the_packages_ship(script: str) -> None:
    named = set(UNIT_NAME.findall(code_of(script)))
    unknown = named - shipped_units()
    assert not unknown, f"{script} names units nothing installs: {sorted(unknown)}"


def test_postinst_enables_every_timer_the_packages_ship() -> None:
    """
    A timer that ships and is never enabled is a job that silently never runs, which is
    exactly how a station stops noticing that updates exist.
    """
    timers = {name for name in shipped_units() if name.endswith(".timer")}
    named = set(UNIT_NAME.findall(code_of("postinst")))
    assert timers <= named, f"postinst never enables {sorted(timers - named)}"


def test_purge_clears_the_enablement_state_of_every_unit_that_ships() -> None:
    """
    deb-systemd-helper remembers whether an owner disabled a unit, in a file outside the
    package. A purge that skipped one would leave that memory behind, and a later install
    would come up with a unit disabled for a reason nobody can see any more.
    """
    named = set(UNIT_NAME.findall(code_of("postrm")))
    assert shipped_units() <= named, f"postrm leaves state behind for {sorted(shipped_units() - named)}"
