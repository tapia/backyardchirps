"""
Decide whether a published version is newer than the running one.

No database and no network: this is the comparison on its own, which is what decides
whether a station shows a badge, and where a development build is easy to get wrong.
"""

import pytest

from backyardchirps.features.updates.logic import is_newer_than_current_version


@pytest.fixture(autouse=True)
def running_version(settings: object) -> None:
    settings.VERSION = "0.2.0"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "published",
    [
        pytest.param("0.2.1", id="a-patch-release"),
        pytest.param("0.3.0", id="a-minor-release"),
        pytest.param("1.0.0", id="a-major-release"),
        pytest.param("0.10.0", id="ten-sorts-above-two-rather-than-as-text"),
    ],
)
def test_a_newer_release_is_an_update(published: str) -> None:
    assert is_newer_than_current_version(published) is True


@pytest.mark.parametrize(
    "published",
    [
        pytest.param("0.2.0", id="the-version-already-running"),
        pytest.param("0.1.9", id="an-older-release"),
        pytest.param("", id="nothing-published-because-the-check-failed"),
        pytest.param("not-a-version", id="something-that-does-not-parse"),
    ],
)
def test_anything_else_is_not(published: str) -> None:
    assert is_newer_than_current_version(published) is False


def test_a_development_build_is_not_offered_the_release_it_was_built_from(settings: object) -> None:
    """
    The case the Pi hits on every push. A build from `main` carries a PEP 440 local
    version, and PEP 440 sorts a local version above the release it is built on, so
    0.2.0+main.abc1234 is already past a published 0.2.0.

    Getting this wrong would show a permanent badge offering an update that is older than
    what the station is running.
    """
    settings.VERSION = "0.2.0+main.abc1234"  # type: ignore[attr-defined]

    assert is_newer_than_current_version("0.2.0") is False
    assert is_newer_than_current_version("0.2.1") is True


def test_an_unparseable_running_version_offers_nothing(settings: object) -> None:
    """
    `VERSION` falls back to 0.0.0+unknown when the package metadata is missing, which
    parses. This is the case where it does not: no comparison is possible, so no update
    is claimed rather than every release looking new.
    """
    settings.VERSION = "whatever-this-is"  # type: ignore[attr-defined]

    assert is_newer_than_current_version("99.0.0") is False
