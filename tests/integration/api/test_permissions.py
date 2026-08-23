from typing import Any
from typing import Callable

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

# Admin-only endpoints: anonymous is rejected, staff is allowed.
_ADMIN_ONLY_PATHS = [
    "/api/settings/",
    "/api/server-status/",
    "/api/species/detection-settings/",
    "/api/updates/available/",
    "/api/updates/progress/",
]

# Public read endpoints: anonymous is allowed.
_PUBLIC_PATHS = [
    "/api/species/",
    "/api/weather/current/",
    "/api/taxonomy/search/?q=turdus",
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


def test_species_detection_settings_put_requires_staff(
    api_client: APIClient, create_detection: Callable[..., Any]
) -> None:
    create_detection(scientific_name="Turdus merula")  # must be detected to reach the staff check

    response = api_client.put("/api/species/turdus-merula/detection-settings/", {"blacklisted": True}, format="json")

    assert response.status_code == 403


def test_applying_an_update_rejects_anonymous(api_client: APIClient) -> None:
    """
    The one endpoint here that starts a root-owned unit. Anonymous must not reach it, and
    it is a POST, so the GET list above cannot cover it.
    """
    assert api_client.post("/api/updates/apply/", {"version": "9.9.9"}, format="json").status_code == 403
