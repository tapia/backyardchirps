"""
The one thing on a station that can act on a change of archive address.

Both the address and the signing key live in the keyring package, so a station that never
installs a newer copy of it can never be told the archive has moved. This script is what
gives that a vehicle, and it runs unattended from a daily timer, which is why what it
refuses to do matters as much as what it does.

Run against stubbed apt rather than read, since the bug that would hurt is a comparison the
wrong way round or an install fired when nothing needed one. The stubs record every command,
so the assertions are about what the script tried to do.
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "packaging" / "bin" / "refresh-keyring"

STUBS = {
    # Prints what apt-cache policy prints, from what the case put in the environment.
    "apt-cache": """#!/bin/sh
echo "$*" >> "$RECORD"
echo "backyardchirps-archive-keyring:"
echo "  Installed: $STUB_INSTALLED"
echo "  Candidate: $STUB_CANDIDATE"
""",
    "apt-get": """#!/bin/sh
echo "$*" >> "$RECORD"
exit "${STUB_APT_GET_RC:-0}"
""",
    # Answers the one question the script asks it. The real ordering is dpkg's own and is
    # held to it in test_repository_pool.py.
    "dpkg": """#!/bin/sh
echo "$*" >> "$RECORD"
[ "$STUB_NEWER" = yes ]
""",
}


@pytest.fixture
def station(tmp_path: Path) -> Path:
    """
    A station with an apt source, and stubbed apt on its PATH.
    """
    (tmp_path / "backyardchirps.sources").write_text("Suites: stable\n", encoding="utf-8")
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    for name, body in STUBS.items():
        stub = stub_dir / name
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)
    return tmp_path


def refresh(station: Path, *, installed: str, candidate: str, newer: str = "yes", apt_get_rc: str = "0") -> list[str]:
    """
    Run the script and give back every command the stubs were asked to run.
    """
    record = station / "record"
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            "PATH": f"{station / 'bin'}:/usr/bin:/bin",
            "RECORD": str(record),
            "SOURCE_FILE": str(station / "backyardchirps.sources"),
            "STUB_INSTALLED": installed,
            "STUB_CANDIDATE": candidate,
            "STUB_NEWER": newer,
            "STUB_APT_GET_RC": apt_get_rc,
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"the script must never fail its caller: {result.stderr}"
    return record.read_text(encoding="utf-8").splitlines() if record.exists() else []


def installs(commands: list[str]) -> list[str]:
    return [command for command in commands if command.startswith("install")]


def test_a_newer_keyring_is_installed(station: Path) -> None:
    commands = refresh(station, installed="1.3", candidate="1.4")

    assert installs(commands), "a newer keyring was offered and nothing installed it"
    assert "backyardchirps-archive-keyring" in installs(commands)[0]


def test_the_lists_are_read_again_after_the_keyring_changed(station: Path) -> None:
    """
    The package has just replaced the source file, and the new one may name a different
    address. Without this the caller compares versions against an archive the station no
    longer reads.
    """
    commands = refresh(station, installed="1.3", candidate="1.4")

    updates = [index for index, command in enumerate(commands) if command.startswith("update")]
    installed_at = commands.index(installs(commands)[0])
    assert any(index > installed_at for index in updates), "the lists were never re-read"


def test_nothing_is_installed_when_the_keyring_is_current(station: Path) -> None:
    commands = refresh(station, installed="1.4", candidate="1.4", newer="no")

    assert not installs(commands)


def test_a_station_with_no_keyring_is_left_alone(station: Path) -> None:
    """
    That is a machine installing from somewhere that does not need one, which is what the
    container suite does with an unsigned local repository. Putting a keyring on it would
    change what it trusts.
    """
    commands = refresh(station, installed="(none)", candidate="1.4")

    assert not installs(commands)


def test_nothing_happens_when_the_repository_offers_no_keyring(station: Path) -> None:
    commands = refresh(station, installed="1.3", candidate="(none)")

    assert not installs(commands)


def test_a_station_with_no_apt_source_is_left_alone(station: Path) -> None:
    os.remove(station / "backyardchirps.sources")

    commands = refresh(station, installed="1.3", candidate="1.4")

    assert commands == []


def test_an_install_that_fails_does_not_fail_the_caller(station: Path) -> None:
    """
    The load-bearing one. This runs inside the daily check, and a keyring that will not
    install must not turn into "the update check failed", which would hide a real update
    behind something unrelated to it.
    """
    commands = refresh(station, installed="1.3", candidate="1.4", apt_get_rc="1")

    assert installs(commands)


def test_the_refresh_is_scoped_to_our_own_source(station: Path) -> None:
    """
    A station polling daily must not refresh, or expire, the sources its owner added for
    something else.
    """
    commands = refresh(station, installed="1.3", candidate="1.4")

    for command in commands:
        if command.startswith("update"):
            assert "Dir::Etc::sourcelist=" in command
            assert "Dir::Etc::sourceparts=/dev/null" in command
