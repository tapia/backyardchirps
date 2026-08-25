from typing import Any
from typing import Callable

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
BLACKBIRD_SLUG = "turdus-merula"

# Admin-only endpoints: anonymous is rejected, staff is allowed.
_ADMIN_ONLY_PATHS = [
    "/api/settings/",
    "/api/server-status/",
    "/api/species/detection-settings/",
    "/api/updates/available/",
    "/api/updates/progress/",
    "/api/detections/dubious/",
    "/api/detections/dubious/count/",
]

# Public read endpoints: anonymous is allowed. Every endpoint is admin-only unless it says
# otherwise, so this list is what stops a dropped AllowAny from going unnoticed.
_PUBLIC_PATHS = [
    "/api/species/",
    "/api/weather/current/",
    "/api/taxonomy/search/?q=turdus",
    "/api/auth/me/",
    "/api/setup/status/",
    "/api/detections/",
    "/api/detections/hourly/",
    "/api/detections/by-hour-of-day/",
    "/api/detections/timeline/",
]

# Public reads that need the species to have been heard at least once. They answer 404
# before that, so they cannot sit in _PUBLIC_PATHS, which runs against an empty database.
_PUBLIC_SPECIES_PATHS = [
    f"/api/species/{BLACKBIRD_SLUG}/",
    f"/api/species/{BLACKBIRD_SLUG}/recordings/",
    f"/api/species/{BLACKBIRD_SLUG}/hourly/",
    f"/api/species/{BLACKBIRD_SLUG}/heatmap/",
    f"/api/species/{BLACKBIRD_SLUG}/yearly/",
    f"/api/species/{BLACKBIRD_SLUG}/seasonality/",
    f"/api/species/{BLACKBIRD_SLUG}/detection-settings/",
]


@pytest.mark.parametrize("path", _ADMIN_ONLY_PATHS)
def test_admin_only_endpoint_rejects_anonymous(api_client: APIClient, path: str) -> None:
    assert api_client.get(path).status_code == 403


@pytest.mark.parametrize("path", _ADMIN_ONLY_PATHS)
def test_admin_only_endpoint_allows_admin(admin_client: APIClient, path: str) -> None:
    assert admin_client.get(path).status_code == 200


@pytest.mark.parametrize("path", _PUBLIC_PATHS)
def test_public_endpoint_allows_anonymous(api_client: APIClient, path: str) -> None:
    assert api_client.get(path).status_code == 200


@pytest.mark.parametrize("path", _PUBLIC_SPECIES_PATHS)
def test_public_species_endpoint_allows_anonymous(
    api_client: APIClient, create_detection: Callable[..., Any], path: str
) -> None:
    create_detection(scientific_name=BLACKBIRD)

    assert api_client.get(path).status_code == 200


def test_species_detection_settings_put_requires_staff(api_client: APIClient) -> None:
    """
    No detection is created first. The permission class runs before the species lookup, so
    a refused write never says whether the station has heard that bird.
    """
    response = api_client.put(
        f"/api/species/{BLACKBIRD_SLUG}/detection-settings/", {"blacklisted": True}, format="json"
    )

    assert response.status_code == 403


def test_applying_an_update_rejects_anonymous(api_client: APIClient) -> None:
    """
    The one endpoint here that starts a root-owned unit. Anonymous must not reach it, and
    it is a POST, so the GET list above cannot cover it.
    """
    assert api_client.post("/api/updates/apply/", {"version": "9.9.9"}, format="json").status_code == 403


def test_rolling_back_rejects_anonymous(api_client: APIClient) -> None:
    """
    The other endpoint that starts a root-owned unit, and the more destructive of the two:
    a rollback across a migration drops everything recorded since the update.
    """
    assert api_client.post("/api/updates/rollback/", {}, format="json").status_code == 403


def test_confirming_a_detection_rejects_anonymous(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    detection = create_detection(scientific_name=BLACKBIRD)

    assert api_client.post(f"/api/detections/{detection.id}/validate/").status_code == 403


def test_bulk_validation_rejects_anonymous(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    """
    The bulk route takes a list of ids, so one unauthenticated call could empty the whole
    queue and every clip behind it.
    """
    detection = create_detection(scientific_name=BLACKBIRD)

    response = api_client.post("/api/detections/validate/", {"action": "discard", "ids": [detection.id]}, format="json")

    assert response.status_code == 403


def test_the_review_queue_rejects_an_ordinary_user(auth_client: APIClient) -> None:
    """
    Being logged in is not enough. Reviewing belongs to whoever runs the station, so an
    account without staff rights cannot even see what is waiting.
    """
    assert auth_client.get("/api/detections/dubious/").status_code == 403
    assert auth_client.get("/api/detections/dubious/count/").status_code == 403


def test_species_detection_settings_put_rejects_an_ordinary_user(
    auth_client: APIClient, create_detection: Callable[..., Any]
) -> None:
    create_detection(scientific_name=BLACKBIRD)

    response = auth_client.put(
        f"/api/species/{BLACKBIRD_SLUG}/detection-settings/", {"blacklisted": True}, format="json"
    )

    assert response.status_code == 403


def test_logging_out_is_open_to_any_logged_in_user(auth_client: APIClient) -> None:
    """
    Everything is admin-only unless it says otherwise, and ending your own session must
    not be: an account without staff rights still has a session to end.
    """
    assert auth_client.post("/api/auth/logout/").status_code == 204
