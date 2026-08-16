from pathlib import Path
from typing import Any
from typing import Callable

import pytest
from rest_framework.test import APIClient

from backyardchirps.features.detections import queries as detection_queries
from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.models.stored_detection import StoredDetection

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"


def test_bulk_confirm_confirms_every_detection(admin_client: APIClient, create_detection: Callable[..., Any]) -> None:
    first = create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING, confidence=0.6)
    second = create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING, confidence=0.5)

    response = admin_client.post(
        "/api/detections/validate/",
        {"action": "confirm", "ids": [first.id, second.id]},
        format="json",
    )

    assert response.status_code == 200
    assert sorted(response.json()["processed"]) == sorted([first.id, second.id])
    for detection_id in (first.id, second.id):
        assert detection_queries.get_by_id(detection_id).validation_status == ValidationStatus.HUMAN_CONFIRMED


def test_bulk_discard_removes_rows_and_clips(
    admin_client: APIClient, create_detection: Callable[..., Any], tmp_path: Path
) -> None:
    clip_file = tmp_path / "clip.wav"
    clip_file.write_bytes(b"audio")
    keep = create_detection(scientific_name=BLACKBIRD)
    drop = create_detection(scientific_name=BLACKBIRD, clip_path=str(clip_file))

    response = admin_client.post(
        "/api/detections/validate/",
        {"action": "discard", "ids": [drop.id]},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["processed"] == [drop.id]
    assert not clip_file.exists()
    assert not StoredDetection.objects.filter(pk=drop.id).exists()
    assert StoredDetection.objects.filter(pk=keep.id).exists()


def test_bulk_action_skips_missing_ids(admin_client: APIClient, create_detection: Callable[..., Any]) -> None:
    detection = create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING, confidence=0.6)

    response = admin_client.post(
        "/api/detections/validate/",
        {"action": "confirm", "ids": [detection.id, 999999]},
        format="json",
    )

    assert response.status_code == 200
    assert response.json()["processed"] == [detection.id]


def test_bulk_unknown_action_is_rejected(admin_client: APIClient, create_detection: Callable[..., Any]) -> None:
    detection = create_detection(scientific_name=BLACKBIRD)

    response = admin_client.post(
        "/api/detections/validate/",
        {"action": "archive", "ids": [detection.id]},
        format="json",
    )

    assert response.status_code == 400


def test_bulk_empty_ids_is_rejected(admin_client: APIClient) -> None:
    response = admin_client.post(
        "/api/detections/validate/",
        {"action": "confirm", "ids": []},
        format="json",
    )

    assert response.status_code == 400
