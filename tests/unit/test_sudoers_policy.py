"""
Hold the sudoers policy install.sh writes to the units the code actually asks for.

The policy is the one place the web process crosses into root, so it is worth pinning
from both ends: nothing in it that the code does not use, and nothing in the code that
it does not cover. `install.sh --print-sudoers` renders it without installing anything,
so this reads what a station is really given rather than parsing the script.
"""

import re
import subprocess
from pathlib import Path

import pytest

from backyardchirps.features.setup import logic as setup_logic
from backyardchirps.integrations.systemd import ALLOWED_UNITS
from backyardchirps.integrations.systemd import restart_unit

INSTALLER = Path(__file__).resolve().parents[2] / "install.sh"

# What every line of the command list has to look like. The path is absolute, since a
# relative one would let PATH decide what runs, and the unit name is one word.
ENTRY_PATTERN = re.compile(r"^/bin/systemctl (start|stop|restart) (\S+)$")

ALLOWED_VERBS = {"start", "stop", "restart"}


@pytest.fixture(scope="module")
def policy() -> str:
    result = subprocess.run(
        ["bash", str(INSTALLER), "--print-sudoers"],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    return result.stdout


def parse_entries(policy: str) -> list[str]:
    """
    The command list, one entry per element, with the line continuations and the user
    specification stripped off.
    """
    flattened = policy.replace("\\\n", " ")
    _, _, command_list = flattened.partition("NOPASSWD:")
    return [entry.strip() for entry in command_list.split(",") if entry.strip()]


def test_the_policy_is_valid_sudoers(policy: str, tmp_path: Path) -> None:
    """
    install.sh runs this check too and refuses to continue when it fails. Running it
    here as well means a broken policy is a red test rather than a failed install on
    somebody's Pi.
    """
    policy_file = tmp_path / "backyardchirps"
    policy_file.write_text(policy)
    result = subprocess.run(
        ["visudo", "-cf", str(policy_file)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, f"{result.stdout}{result.stderr}"


def test_every_entry_is_one_fully_qualified_command(policy: str) -> None:
    for entry in parse_entries(policy):
        assert ENTRY_PATTERN.match(entry), f"unexpected entry: {entry}"


def test_the_policy_carries_no_wildcard(policy: str) -> None:
    """
    The check this file was written for.

    `backyardchirps-*` reads like "our units" and is not: sudo matches the arguments as
    one concatenated string, so the wildcard runs across spaces and
    `systemctl restart backyardchirps-web nginx` matches it too. It would also
    pre-approve any unit added later whose name starts with the prefix, which is how a
    root-owned updater could become callable by the web process without anyone deciding
    that it should be.
    """
    for character in "*?[]":
        assert character not in policy, f"the policy contains {character!r}: {policy}"


def test_the_policy_names_the_units_the_code_knows_about(policy: str) -> None:
    units = {ENTRY_PATTERN.match(entry).group(2) for entry in parse_entries(policy)}  # type: ignore[union-attr]
    assert units == set(ALLOWED_UNITS)


def test_the_policy_grants_no_verb_beyond_start_stop_and_restart(policy: str) -> None:
    verbs = {ENTRY_PATTERN.match(entry).group(1) for entry in parse_entries(policy)}  # type: ignore[union-attr]
    assert verbs <= ALLOWED_VERBS


def test_the_unit_the_wizard_restarts_is_covered(policy: str) -> None:
    """
    The one grant the station cannot do without: the wizard restarts the recorder after
    the settings that the recorder caches at startup have changed.
    """
    assert f"/bin/systemctl restart {setup_logic.RECORDER_UNIT}" in parse_entries(policy)


def test_a_unit_outside_the_list_is_refused_without_calling_sudo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("sudo was called for a unit that is not allowed")

    monkeypatch.setattr(subprocess, "run", fail)
    assert restart_unit("nginx") is False
    assert restart_unit("backyardchirps-web nginx") is False
