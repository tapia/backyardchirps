"""
Hold the sudoers policy the package ships to the units the code actually asks for.

The policy is the one place the web process crosses into root, so it is worth pinning
from both ends: nothing in it that the code does not use, and nothing in the code that
it does not cover. This reads the file itself, which is the exact bytes a station is
given: the package installs it verbatim rather than rendering it from anything.
"""

import re
import subprocess
from pathlib import Path

import pytest

from backyardchirps.features.setup import logic as setup_logic
from backyardchirps.integrations.systemd import MANAGED_UNITS
from backyardchirps.integrations.systemd import restart_unit
from backyardchirps.integrations.systemd import start_unit

POLICY_FILE = Path(__file__).resolve().parents[2] / "packaging" / "sudoers" / "backyardchirps"

# What every line of the command list has to look like. The path is absolute, since a
# relative one would let PATH decide what runs, and the unit name is one word.
ENTRY_PATTERN = re.compile(r"^/bin/systemctl (start|stop|restart) (\S+)$")

ALLOWED_VERBS = {"start", "stop", "restart"}


@pytest.fixture(scope="module")
def policy() -> str:
    return POLICY_FILE.read_text(encoding="utf-8")


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
    postinst runs this check too, and removes the file and fails when it does not pass:
    sudo refuses to read the whole of /etc/sudoers.d when one entry in it does not parse.
    Running it here as well means a broken policy is a red test rather than a package that
    will not configure on somebody's Pi.
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

    The command list rather than the whole file: the comments above it name the pattern
    they are warning about, and a comment grants nothing.
    """
    for entry in parse_entries(policy):
        for character in "*?[]":
            assert character not in entry, f"the policy contains {character!r}: {entry}"


def test_the_policy_grants_exactly_the_pairs_the_code_knows_about(policy: str) -> None:
    """
    Pairs, not just unit names. The updater runs as root and replaces the release, so it
    is granted `start` alone: a policy that quietly gave it `stop` as well would let the
    web process kill an update half way through, and a unit-only check would not notice.
    """
    granted = set()
    for entry in parse_entries(policy):
        match = ENTRY_PATTERN.match(entry)
        assert match, f"unexpected entry: {entry}"
        granted.add((match.group(2), match.group(1)))

    expected = {(unit, verb) for unit, verbs in MANAGED_UNITS.items() for verb in verbs}
    assert granted == expected


def test_the_policy_grants_no_verb_beyond_start_stop_and_restart(policy: str) -> None:
    verbs = {ENTRY_PATTERN.match(entry).group(1) for entry in parse_entries(policy)}  # type: ignore[union-attr]
    assert verbs <= ALLOWED_VERBS


def test_the_updater_may_be_started_and_nothing_more(policy: str) -> None:
    entries = parse_entries(policy)

    assert "/bin/systemctl start backyardchirps-update" in entries
    assert "/bin/systemctl stop backyardchirps-update" not in entries
    assert "/bin/systemctl restart backyardchirps-update" not in entries


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
    # Granted start, so restarting it has to be refused by the verb rather than the unit.
    assert restart_unit("backyardchirps-update") is False


def test_the_updater_can_be_started_through_the_verb_it_was_granted(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[list[str]] = []

    def record(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        called.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", record)

    assert start_unit("backyardchirps-update") is True
    assert called == [["sudo", "systemctl", "start", "backyardchirps-update"]]
