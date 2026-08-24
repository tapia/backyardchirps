"""
The two version orderings a station depends on agreeing.

A package version and the version the site reports are the same string. PEP 440 decides
which release the updater thinks is newer, and dpkg decides which one apt will install, so
a case where the two disagree is a station that either refuses an upgrade or takes one it
should not. These are the cases that could plausibly come up.

`dpkg --compare-versions` is the authority, so this is skipped where dpkg is not installed,
which is a developer's laptop. CI runs on Debian and does not skip.
"""

import shutil
import subprocess

import pytest
from packaging.version import Version

pytestmark = pytest.mark.skipif(shutil.which("dpkg") is None, reason="dpkg is not installed on this machine")

# Every pair is (older, newer). A build off main carries a PEP 440 local version, which is
# the mechanism that keeps it from ever being mistaken for the release it was cut from.
ORDERED_PAIRS = [
    ("0.2.0", "0.3.0"),
    ("0.2.0", "0.2.1"),
    ("0.9.0", "0.10.0"),
    ("0.2.0", "0.2.0+main.abc1234"),
    ("0.2.0+main.abc1234", "0.2.1"),
    ("0.2.0+main.abc1234", "0.2.0+main.bcd2345"),
]


def dpkg_says_older(older: str, newer: str) -> bool:
    return (
        subprocess.run(["dpkg", "--compare-versions", older, "lt", newer], check=False, capture_output=True).returncode
        == 0
    )


@pytest.mark.parametrize(("older", "newer"), ORDERED_PAIRS)
def test_dpkg_and_pep_440_agree_on_what_is_newer(older: str, newer: str) -> None:
    assert Version(older) < Version(newer), f"PEP 440 does not read {newer} as newer than {older}"
    assert dpkg_says_older(older, newer), f"dpkg does not read {newer} as newer than {older}"


def test_a_pre_bumped_version_would_break_the_ordering() -> None:
    """
    The trap this file exists for. This project bumps pyproject.toml at release time, so a
    build off main is always a local version of the *previous* release and sorts below the
    next one. Pre-bumping the version before cutting the release inverts that: main builds
    would sort above the release and every station would refuse to move to it.

    Debian's idiom for "sorts below" is a tilde, which is not valid PEP 440, so the two
    version strings would have to come apart to fix it. Keep the bump at release time
    instead, and this stays a note rather than a problem.
    """
    pre_bumped_main_build = "0.3.0+main.abc1234"
    the_eventual_release = "0.3.0"

    assert not dpkg_says_older(pre_bumped_main_build, the_eventual_release)
    assert not Version(pre_bumped_main_build) < Version(the_eventual_release)
