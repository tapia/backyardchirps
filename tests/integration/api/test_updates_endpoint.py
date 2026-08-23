"""
What /api/updates/available/ tells the UI, in each of the three states a station can be
in: never checked, checked and current, checked and behind.
"""

import pytest
from rest_framework.test import APIClient

from backyardchirps.features.updates import queries as updates_queries
from backyardchirps.integrations import updates as updates_integration

_URL = "/api/updates/available/"

MANIFEST = {
    "version": "9.9.9",
    "released": "2026-08-23",
    "changelog_url": "https://example.com/releases/tag/v9.9.9",
}


def test_a_station_that_has_never_checked_says_so(admin_client: APIClient) -> None:
    """
    checked_at is null rather than the response claiming the station is up to date. Those
    are different things, and only one of them is worth acting on.
    """
    body = admin_client.get(_URL).json()

    assert body["checked_at"] is None
    assert body["update_available"] is False
    assert body["version"] == ""


def test_a_newer_release_is_offered(admin_client: APIClient, settings: object) -> None:
    settings.VERSION = "0.2.0"  # type: ignore[attr-defined]
    updates_queries.record_result(MANIFEST)

    body = admin_client.get(_URL).json()

    assert body["update_available"] is True
    assert body["version"] == "9.9.9"
    assert body["released"] == "2026-08-23"
    assert body["changelog_url"] == MANIFEST["changelog_url"]
    assert body["running_version"] == "0.2.0"
    assert body["checked_at"] is not None


def test_the_release_a_station_already_runs_is_not_an_update(admin_client: APIClient, settings: object) -> None:
    settings.VERSION = "9.9.9"  # type: ignore[attr-defined]
    updates_queries.record_result(MANIFEST)

    body = admin_client.get(_URL).json()

    assert body["update_available"] is False
    assert body["version"] == "9.9.9"


def test_a_failed_check_is_reported_as_a_failure(admin_client: APIClient) -> None:
    updates_queries.record_failure("ConnectionError")

    body = admin_client.get(_URL).json()

    assert body["error"] == "ConnectionError"
    assert body["update_available"] is False
    assert body["checked_at"] is not None


def test_reading_it_never_reaches_the_network(admin_client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The timer owns the request to GitHub. If opening the page made one, four people
    looking at a station would be four requests, on a web process with four slots.
    """

    def fail() -> dict[str, str]:
        raise AssertionError("the endpoint fetched the manifest")

    monkeypatch.setattr(updates_integration, "fetch_manifest", fail)

    assert admin_client.get(_URL).status_code == 200
