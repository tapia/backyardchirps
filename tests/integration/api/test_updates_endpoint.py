"""
What /api/updates/available/ tells the UI, in each of the three states a station can be
in: never checked, checked and current, checked and behind.

The verdict itself is not made here. apt decides which of two versions is newer, the check
writes that answer down, and this endpoint reads it, so what these hold is that the stored
answer reaches the page unchanged.
"""

import dataclasses
from typing import Any

import pytest
from rest_framework.test import APIClient

from backyardchirps.features.updates import logic as updates_logic
from backyardchirps.features.updates import queries as updates_queries
from backyardchirps.features.updates.entity import UpdateCheckResult

_URL = "/api/updates/available/"
_CHECK_URL = "/api/updates/check/"

FOUND = UpdateCheckResult(
    version="9.9.9",
    released="2026-08-23",
    changelog_url="https://example.com/releases/tag/v9.9.9",
    update_available=True,
    error="",
)


def test_a_station_that_has_never_checked_says_so(admin_client: APIClient) -> None:
    """
    checked_at is null rather than the response claiming the station is up to date. Those
    are different things, and only one of them is worth acting on.
    """
    body = admin_client.get(_URL).json()

    assert body["checked_at"] is None
    assert body["update_available"] is False
    assert body["version"] == ""


def test_a_newer_version_is_offered(admin_client: APIClient, settings: Any) -> None:
    settings.VERSION = "0.2.0"
    updates_queries.record_result(FOUND)

    body = admin_client.get(_URL).json()

    assert body["update_available"] is True
    assert body["version"] == "9.9.9"
    assert body["released"] == "2026-08-23"
    assert body["changelog_url"] == FOUND.changelog_url
    assert body["running_version"] == "0.2.0"
    assert body["checked_at"] is not None


def test_the_version_a_station_already_runs_is_not_an_update(admin_client: APIClient, settings: Any) -> None:
    """
    What apt found is still shown. The badge is what goes away, and it goes away because
    the check said so rather than because this endpoint compared anything.
    """
    settings.VERSION = "9.9.9"
    updates_queries.record_result(dataclasses.replace(FOUND, update_available=False))

    body = admin_client.get(_URL).json()

    assert body["update_available"] is False
    assert body["version"] == "9.9.9"


def test_a_failed_check_is_reported_as_a_failure(admin_client: APIClient) -> None:
    updates_queries.record_result(
        UpdateCheckResult(
            version="", released="", changelog_url="", update_available=False, error="unreachable_repository"
        )
    )

    body = admin_client.get(_URL).json()

    assert body["error"] == "unreachable_repository"
    assert body["update_available"] is False
    assert body["checked_at"] is not None


def test_reading_it_never_talks_to_apt(admin_client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The unit owns the conversation with the repository. If opening the page started it,
    four people looking at a station would be four apt runs, on a web process with four
    slots, and the page would take as long as the slowest of them.
    """

    def fail(unit: str) -> bool:
        raise AssertionError(f"the endpoint started {unit}")

    monkeypatch.setattr(updates_logic, "start_unit", fail)

    assert admin_client.get(_URL).status_code == 200


def test_checking_now_runs_the_privileged_unit_and_answers_with_what_it_found(
    admin_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The unit is a oneshot, so starting it waits for it to finish. By the time this answers
    the stored result is the fresh one, and the page needs no second request.
    """
    started: list[str] = []

    def start(unit: str) -> bool:
        updates_queries.record_result(FOUND)
        started.append(unit)
        return True

    monkeypatch.setattr(updates_logic, "start_unit", start)

    body = admin_client.post(_CHECK_URL).json()

    assert started == [updates_logic.CHECK_UNIT]
    assert body["update_available"] is True
    assert body["version"] == "9.9.9"


def test_a_check_that_could_not_be_started_is_refused_rather_than_reported_as_no_update(
    admin_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(updates_logic, "start_unit", lambda unit: False)

    response = admin_client.post(_CHECK_URL)

    assert response.status_code == 409
    assert response.json()["error"] == "could_not_start_check"
