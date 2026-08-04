from typing import Any
from typing import Callable

import pytest
from rest_framework.test import APIClient

from backyardchirps.features.overrides import queries as species_override_repository
from backyardchirps.features.species.entity import Species

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
BLACKBIRD_SLUG = "turdus-merula"
_PATH = f"/api/species/{BLACKBIRD_SLUG}/detection-settings/"


def test_get_returns_default_state(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD)

    response = api_client.get(_PATH)

    assert response.status_code == 200
    assert response.data == {"blacklisted": False, "auto_confirm_threshold": None}


def test_admin_put_sets_override(admin_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD)

    response = admin_client.put(_PATH, {"auto_confirm_threshold": 0.6, "blacklisted": True}, format="json")

    assert response.status_code == 200
    assert response.data == {"blacklisted": True, "auto_confirm_threshold": 0.6}
    override = species_override_repository.get(Species(BLACKBIRD))
    assert override is not None
    assert override.auto_confirm_threshold == 0.6
    assert override.blacklisted is True


def test_admin_put_invalid_threshold_returns_400(admin_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD)

    response = admin_client.put(_PATH, {"auto_confirm_threshold": 1.5}, format="json")

    assert response.status_code == 400
    assert "error" in response.data


def test_admin_delete_clears_override(
    admin_client: APIClient, create_detection: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    create_detection(scientific_name=BLACKBIRD)
    create_override(scientific_name=BLACKBIRD, threshold=0.5)

    response = admin_client.delete(_PATH)

    assert response.status_code == 204
    assert species_override_repository.get(Species(BLACKBIRD)) is None


def test_detection_settings_list_returns_customized_species(
    admin_client: APIClient, create_detection: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    create_detection(scientific_name=BLACKBIRD)
    create_override(scientific_name=BLACKBIRD, blacklisted=True)

    response = admin_client.get("/api/species/detection-settings/")

    assert response.status_code == 200
    assert [entry["scientific_name"] for entry in response.data["species"]] == [BLACKBIRD]
