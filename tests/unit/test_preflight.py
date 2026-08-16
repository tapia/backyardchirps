"""
Run install.sh's machine checks against fixtures and assert what they decide.

install.sh reads the machine through five overridable values, and --preflight-only runs the
checks and stops, before the root check and before anything is written. Pointing those
values at files in a temporary directory is what makes the checks testable from anywhere,
which is the point: this runs on a laptop and on an x86 CI runner, neither of which is a
Raspberry Pi.
"""

import os
import subprocess
from pathlib import Path

import pytest

INSTALLER = Path(__file__).resolve().parents[2] / "install.sh"

# The four files and the one string the checks read. Every case below is this machine with
# one value changed: a Pi 5 on trixie with a USB microphone, which is a station that works.
WORKING_STATION = {
    "DEVICE_TREE_MODEL_FILE": "model-pi5",
    "OS_RELEASE_FILE": "os-trixie",
    "ASOUND_PCM_FILE": "pcm-with-microphone",
    "RPI_ISSUE_FILE": "rpi-issue",
    "SYSTEM_ARCHITECTURE": "arm64",
}

# One file each. "absent" is deliberately never written: it is what a case names to say the
# file is not on this machine.
#
# /proc/device-tree/model is NUL-terminated on a real Pi, which is why install.sh strips
# NULs before matching it. Written the same way here.
#
# Raspberry Pi OS 64-bit carries Debian's own os-release, word for word. That is the
# fixture that matters: it is what the old check could never match.
FIXTURE_FILES = {
    "model-pi5": "Raspberry Pi 5 Model B Rev 1.1\0",
    "model-pi4": "Raspberry Pi 4 Model B Rev 1.5\0",
    "model-pi3": "Raspberry Pi 3 Model B Plus Rev 1.3\0",
    "os-trixie": (
        'PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\n'
        'NAME="Debian GNU/Linux"\n'
        'VERSION_ID="13"\n'
        'VERSION="13 (trixie)"\n'
        "VERSION_CODENAME=trixie\n"
        "ID=debian\n"
    ),
    "os-forky": ('PRETTY_NAME="Debian GNU/Linux 14 (forky)"\nVERSION_ID="14"\nID=debian\n'),
    "os-bookworm": ('PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\nVERSION_ID="12"\nID=debian\n'),
    "os-raspbian": ('PRETTY_NAME="Raspbian GNU/Linux 12 (bookworm)"\nVERSION_ID="12"\nID=raspbian\nID_LIKE=debian\n'),
    "os-ubuntu": ('PRETTY_NAME="Ubuntu 24.04.1 LTS"\nVERSION_ID="24.04"\nID=ubuntu\nID_LIKE=debian\n'),
    "os-sid": 'PRETTY_NAME="Debian GNU/Linux trixie/sid"\nID=debian\n',
    # A Pi 5 has two HDMI playback devices whether or not anything can record, which is why
    # the check counts capture lines rather than cards.
    "pcm-with-microphone": (
        "00-00: vc4-hdmi-0 i2s-hifi-0 :  : playback 1\n"
        "01-00: vc4-hdmi-1 i2s-hifi-0 :  : playback 1\n"
        "02-00: USB Audio : USB Audio : capture 1\n"
    ),
    "pcm-hdmi-only": ("00-00: vc4-hdmi-0 i2s-hifi-0 :  : playback 1\n01-00: vc4-hdmi-1 i2s-hifi-0 :  : playback 1\n"),
    "rpi-issue": "Raspberry Pi reference 2026-08-01\n",
}


@pytest.fixture(scope="session")
def machine_fixtures(tmp_path_factory: pytest.TempPathFactory) -> Path:
    directory = tmp_path_factory.mktemp("preflight")
    for name, content in FIXTURE_FILES.items():
        (directory / name).write_text(content)
    return directory


def run_preflight(
    machine_fixtures: Path,
    overrides: dict[str, str],
    extra_flags: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    """
    Run the machine checks with every input pointed at a fixture and nothing else.

    A value for one of the four *_FILE variables is a fixture name, resolved here, so a
    case can say "model-pi4" rather than repeat the temporary directory. SYSTEM_ARCHITECTURE
    is passed through as it is, being a string the installer compares rather than a path.
    """
    environment = dict(os.environ)
    for key, value in {**WORKING_STATION, **overrides}.items():
        environment[key] = str(machine_fixtures / value) if key.endswith("_FILE") else value

    return subprocess.run(
        ["bash", str(INSTALLER), "--preflight-only", *extra_flags],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def report(result: subprocess.CompletedProcess[str]) -> str:
    """
    Everything the installer said, for the assertion message. `die` writes to stderr and the
    checks themselves write to stdout, so a failure needs both to explain itself.
    """
    return f"exit {result.returncode}\n{result.stdout}{result.stderr}"


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({}, id="pi-5-on-trixie-with-a-microphone"),
        pytest.param({"DEVICE_TREE_MODEL_FILE": "model-pi4"}, id="pi-4-is-supported-too"),
        pytest.param({"OS_RELEASE_FILE": "os-forky"}, id="debian-newer-than-trixie"),
        # Pi OS images carry /etc/rpi-issue and plain Debian on a Pi does not. That
        # combination is untested rather than known broken, so it passes with a note.
        pytest.param({"RPI_ISSUE_FILE": "absent"}, id="plain-debian-on-a-pi"),
    ],
)
def test_machine_is_accepted(machine_fixtures: Path, overrides: dict[str, str]) -> None:
    result = run_preflight(machine_fixtures, overrides)
    assert result.returncode == 0, f"expected this machine to be accepted:\n{report(result)}"


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        pytest.param(
            {"DEVICE_TREE_MODEL_FILE": "model-pi3"},
            "Unsupported board",
            id="a-pi-3-is-refused-by-name",
        ),
        pytest.param(
            {"DEVICE_TREE_MODEL_FILE": "absent"},
            "does not look like a Raspberry Pi",
            id="not-a-pi-at-all",
        ),
        pytest.param(
            {"SYSTEM_ARCHITECTURE": "armhf"},
            "needs 64-bit",
            id="32-bit-is-refused",
        ),
        pytest.param(
            {"OS_RELEASE_FILE": "os-bookworm"},
            "Debian 13",
            id="bookworm-ships-too-old-a-python",
        ),
        pytest.param(
            {"OS_RELEASE_FILE": "os-ubuntu"},
            "reports itself as Debian",
            id="ubuntu-despite-id-like-debian",
        ),
        pytest.param(
            {"OS_RELEASE_FILE": "os-raspbian"},
            "reports itself as Debian",
            id="32-bit-raspbian",
        ),
        pytest.param(
            {"OS_RELEASE_FILE": "os-sid"},
            "gives no version to check",
            id="an-unnumbered-debian-cannot-be-judged",
        ),
        pytest.param(
            {"OS_RELEASE_FILE": "absent"},
            "nothing in /etc/os-release",
            id="no-os-release-at-all",
        ),
        pytest.param(
            {"ASOUND_PCM_FILE": "pcm-hdmi-only"},
            "No capture device",
            id="hdmi-playback-alone-is-not-a-microphone",
        ),
        pytest.param(
            {"ASOUND_PCM_FILE": "absent"},
            "No capture device",
            id="no-alsa-at-all",
        ),
    ],
)
def test_machine_is_refused(machine_fixtures: Path, overrides: dict[str, str], expected_reason: str) -> None:
    """
    The reason is asserted along with the refusal, so a check that starts failing for a
    different reason than the one under test cannot quietly keep passing.
    """
    result = run_preflight(machine_fixtures, overrides)

    assert result.returncode != 0, f"expected a refusal, but the machine was accepted:\n{report(result)}"
    assert expected_reason in report(result), f"refused, but not for the reason expected:\n{report(result)}"


def test_ignore_preflight_skips_every_check(machine_fixtures: Path) -> None:
    """
    The container test depends on this, and so does anyone setting a station up before the
    microphone arrives. Every value below is wrong on purpose.
    """
    result = run_preflight(
        machine_fixtures,
        {
            "DEVICE_TREE_MODEL_FILE": "absent",
            "OS_RELEASE_FILE": "os-ubuntu",
            "ASOUND_PCM_FILE": "absent",
            "SYSTEM_ARCHITECTURE": "amd64",
        },
        extra_flags=("--ignore-preflight",),
    )

    assert result.returncode == 0, f"--ignore-preflight did not skip the checks:\n{report(result)}"
    assert "Hardware checks skipped." in result.stdout
