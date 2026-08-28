from typing import Any
from typing import Callable

import pytest
from rest_framework.test import APIClient

from backyardchirps.features.detections import queries as detection_queries
from backyardchirps.features.detections.entity import ValidationStatus

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


def test_lowering_the_auto_confirm_bar_publishes_what_was_waiting(
    admin_client: APIClient, create_detection: Callable[..., Any]
) -> None:
    pending = create_detection(confidence=0.85, validation_status=ValidationStatus.PENDING)

    response = admin_client.put(_SETTINGS_PATH, {"analysis_auto_confirm_confidence": "0.8"}, format="json")

    assert response.data["published_from_queue"] == 1
    assert detection_queries.get_by_id(pending.id).validation_status == ValidationStatus.AUTO_CONFIRMED
