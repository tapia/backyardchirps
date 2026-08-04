import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

_SETTINGS_PATH = "/api/settings/"


def test_admin_get_returns_all_settings(admin_client: APIClient) -> None:
    response = admin_client.get(_SETTINGS_PATH)

    assert response.status_code == 200
    assert response.data["notifications_language"] == "es"  # default


def test_admin_put_valid_subset_persists(admin_client: APIClient) -> None:
    response = admin_client.put(_SETTINGS_PATH, {"notifications_language": "en"}, format="json")

    assert response.status_code == 200
    assert response.data["notifications_language"] == "en"
    assert admin_client.get(_SETTINGS_PATH).data["notifications_language"] == "en"


def test_admin_put_invalid_value_reports_field_error(admin_client: APIClient) -> None:
    response = admin_client.put(_SETTINGS_PATH, {"notifications_language": "xx"}, format="json")

    assert response.status_code == 400
    assert "notifications_language" in response.data["errors"]


def test_admin_put_unknown_key_reports_error(admin_client: APIClient) -> None:
    response = admin_client.put(_SETTINGS_PATH, {"not_a_setting": "1"}, format="json")

    assert response.status_code == 400
    assert "not_a_setting" in response.data["errors"]
