"""
Run a check and see what it stores.

The network call is stubbed at the integration boundary, so what is under test is the
workflow around it: a good manifest is kept, a failure is recorded as one, and neither
raises out of a job that runs unattended from a timer.
"""

from typing import Any

import pytest
import requests

from backyardchirps.features.updates import logic as updates_logic
from backyardchirps.features.updates import queries as updates_queries
from backyardchirps.integrations import updates as updates_integration

pytestmark = pytest.mark.django_db

MANIFEST = {
    "version": "9.9.9",
    "released": "2026-08-23",
    "sha256": "0" * 64,
    "url": "https://example.com/backyardchirps-9.9.9.tar.zst",
    "min_upgrade_from": "0.1.0",
    "changelog_url": "https://example.com/releases/tag/v9.9.9",
}


def stub_manifest(monkeypatch: pytest.MonkeyPatch, manifest: dict[str, Any]) -> None:
    monkeypatch.setattr(updates_integration, "fetch_manifest", lambda: manifest)


def stub_failure(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def fail() -> dict[str, Any]:
        raise error

    monkeypatch.setattr(updates_integration, "fetch_manifest", fail)


def test_a_station_that_has_never_checked_reports_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    assert updates_queries.last_check() is None


def test_a_good_manifest_is_stored_and_read_back(monkeypatch: pytest.MonkeyPatch) -> None:
    stub_manifest(monkeypatch, MANIFEST)

    result = updates_logic.check_for_update()

    assert result.succeeded
    assert result.version == "9.9.9"
    assert result.released == "2026-08-23"
    assert result.changelog_url == MANIFEST["changelog_url"]

    stored = updates_queries.last_check()
    assert stored is not None
    assert stored.version == "9.9.9"


def test_checking_twice_leaves_one_result(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A row per check would grow without bound on a station that runs one every day and is
    never looked at, and nothing reads any result but the newest.
    """
    stub_manifest(monkeypatch, MANIFEST)
    updates_logic.check_for_update()
    stub_manifest(monkeypatch, {**MANIFEST, "version": "9.9.10"})
    updates_logic.check_for_update()

    stored = updates_queries.last_check()
    assert stored is not None
    assert stored.version == "9.9.10"


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(requests.ConnectionError("no route to host"), id="a-station-with-no-internet"),
        pytest.param(requests.Timeout("took too long"), id="a-request-that-hung"),
        pytest.param(requests.HTTPError("404"), id="no-manifest-published-yet"),
        pytest.param(ValueError("The release manifest is not a JSON object."), id="something-that-is-not-a-manifest"),
    ],
)
def test_a_failed_check_is_recorded_rather_than_raised(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    stub_failure(monkeypatch, error)

    result = updates_logic.check_for_update()

    assert not result.succeeded
    assert result.error == type(error).__name__
    assert result.version == ""


def test_a_failure_clears_the_version_an_earlier_check_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Showing a version found days ago beside "the check is failing" invites reading the
    first and ignoring the second, and the station cannot tell whether it is still the
    latest.
    """
    stub_manifest(monkeypatch, MANIFEST)
    updates_logic.check_for_update()
    stub_failure(monkeypatch, requests.ConnectionError("no route to host"))
    updates_logic.check_for_update()

    stored = updates_queries.last_check()
    assert stored is not None
    assert stored.version == ""
    assert stored.error == "ConnectionError"


def test_a_manifest_missing_the_fields_we_read_does_not_break_the_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The release workflow owns the manifest's shape. A station has to survive one that has
    changed, and answering "no update" is the safe way to be wrong.
    """
    stub_manifest(monkeypatch, {"unexpected": "shape"})

    result = updates_logic.check_for_update()

    assert result.succeeded
    assert result.version == ""
    assert updates_logic.is_newer_than_current_version(result.version) is False
