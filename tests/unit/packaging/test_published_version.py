"""
Hold the two workflows that need the version of a build off main to one rule for composing it.

The bug this exists for cost two failed runs. Publish and Deploy each worked the string out
themselves, from the version in pyproject.toml and the commit sha. That is the same rule
written twice, so the moment one copy changed the other went on asking for a version that had
never been built, and the install on the Pi failed with "not found" ten minutes later.

Reading the workflow files is unusual for a test, and it is the point here: what went wrong
was not what either file said but that both said it.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# The one command that composes it. Both workflows run this and read what it prints.
COMPOSER = "tools/build_packages.py --print-main-version"

# Anything that looks like a workflow building the local version out of parts of its own.
COMPOSED_BY_HAND = re.compile(r"\+\$?\{?(main|SUITE)")


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", ["publish.yml", "deploy.yml"])
def test_the_version_of_a_main_build_comes_from_one_command(name: str) -> None:
    assert COMPOSER in workflow(name), f"{name} does not ask for the version, so it works it out itself"


@pytest.mark.parametrize("name", ["publish.yml", "deploy.yml"])
def test_no_workflow_builds_the_version_out_of_parts(name: str) -> None:
    lines = [line for line in workflow(name).splitlines() if not line.lstrip().startswith("#")]
    hand_rolled = [line.strip() for line in lines if COMPOSED_BY_HAND.search(line)]
    assert not hand_rolled, f"{name} composes a version itself: {hand_rolled}"


def test_the_composer_prints_a_version_and_nothing_else() -> None:
    """
    Both workflows read it with a plain command substitution, so a second line of output, or
    a progress message on stdout, would end up inside a version string.
    """
    printed = subprocess.run(
        ["python", str(REPO_ROOT / "tools" / "build_packages.py"), "--print-main-version"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )

    assert printed.stdout.count("\n") == 1
    # The version in pyproject.toml, then main, then the commit count, then the short sha.
    assert re.fullmatch(r"\d+\.\d+\.\d+\+main\.\d+\.[0-9a-f]{7}", printed.stdout.strip()), printed.stdout
