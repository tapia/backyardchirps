"""
install.sh's --suite flag, and the seam it sits on.

The flag decides one thing: which suite a fresh machine ends up following. It does that by
writing a file the keyring package's postinst reads, so the two have to agree on the path
and on which names are allowed. Nothing checks that agreement at build time, and a drift
would be quiet: the installer would write a choice nobody reads, and the station would come
up on stable while its owner believed otherwise.

Everything here runs before the root check, so it works on a laptop.
"""

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER = REPO_ROOT / "install.sh"
KEYRING_POSTINST = REPO_ROOT / "packaging" / "apt" / "postinst"


def run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(INSTALLER), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def assignment(script: Path, name: str) -> str:
    """
    The value a shell script assigns to a variable, with any ${VAR:-default} unwrapped.
    """
    match = re.search(rf'(?m)^{name}="?(?:\$\{{{name}:-)?([^"}}\n]+)', script.read_text(encoding="utf-8"))
    assert match is not None, f"{script.name} does not assign {name}"
    return match.group(1).strip()


def test_a_suite_that_does_not_exist_is_refused_before_anything_is_written() -> None:
    result = run("--suite", "untsable")

    assert result.returncode != 0
    assert "Unknown suite" in result.stderr
    assert "stable unstable" in result.stderr


def test_the_help_describes_the_flag() -> None:
    result = run("--help")

    assert result.returncode == 0
    assert "--suite" in result.stdout


def test_the_installer_and_the_postinst_agree_on_where_the_channel_lives() -> None:
    """
    One writes it and the other reads it, in different languages and different packages. A
    rename on one side leaves a file nobody reads and a station quietly on stable.
    """
    assert assignment(INSTALLER, "CHANNEL_FILE") == assignment(KEYRING_POSTINST, "CHANNEL_FILE")


def test_the_installer_and_the_postinst_allow_the_same_suites() -> None:
    """
    The installer refusing a name the postinst would have taken is only annoying. The other
    way round is worse: a name that passes here and is rejected on the station leaves a
    machine on stable with the reason buried in an install log.
    """
    assert assignment(INSTALLER, "KNOWN_SUITES") == assignment(KEYRING_POSTINST, "KNOWN_CHANNELS")


def test_the_default_is_releases_only() -> None:
    """
    What an owner's machine gets when nobody passes anything.
    """
    assert assignment(INSTALLER, "SUITE") == "stable"
    assert assignment(KEYRING_POSTINST, "DEFAULT_CHANNEL") == "stable"


def test_the_channel_is_written_before_the_keyring_package_is_installed() -> None:
    """
    The order is the whole mechanism. The postinst reads the channel once, when dpkg
    configures the package, so a channel written afterwards is a channel nobody reads until
    somebody reinstalls that package by hand.
    """
    text = INSTALLER.read_text(encoding="utf-8")

    written = text.index('> "$CHANNEL_FILE"')
    installed = text.index('dpkg -i "$work_dir/keyring.deb"')

    assert written < installed, "install.sh installs the keyring package before writing the channel"
