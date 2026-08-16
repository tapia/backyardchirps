from datetime import datetime
from datetime import timezone
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
ROBIN = "Erithacus rubecula"


def test_admin_post_confirms_detection(admin_client: APIClient, create_detection: Callable[..., Any]) -> None:
    detection = create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING, confidence=0.6)

    response = admin_client.post(f"/api/detections/{detection.id}/validate/")

    assert response.status_code == 200
    assert detection_queries.get_by_id(detection.id).validation_status == ValidationStatus.HUMAN_CONFIRMED


def test_admin_post_reassigning_into_the_same_recording_is_rejected(
    admin_client: APIClient, create_detection: Callable[..., Any]
) -> None:
    """
    The dialog keeps these species unselectable, so a request that asks for one
    anyway is malformed and gets an error rather than a silent deletion.
    """
    recorded_at = datetime(2024, 6, 15, 8, 7, 31, tzinfo=timezone.utc)
    create_detection(scientific_name=ROBIN, recorded_at=recorded_at, confidence=0.95)
    blackbird = create_detection(
        scientific_name=BLACKBIRD,
        recorded_at=recorded_at,
        validation_status=ValidationStatus.PENDING,
    )

    response = admin_client.post(
        f"/api/detections/{blackbird.id}/validate/",
        {"species_scientific_name": ROBIN},
        format="json",
    )

    assert response.status_code == 400
    assert "species_scientific_name" in response.json()
    unchanged = detection_queries.get_by_id(blackbird.id)
    assert unchanged.validation_status == ValidationStatus.PENDING
    assert StoredDetection.objects.filter(species__scientific_name=ROBIN).count() == 1


def test_admin_delete_discards_detection_and_clip(
    admin_client: APIClient, create_detection: Callable[..., Any], tmp_path: Path
) -> None:
    clip_file = tmp_path / "clip.wav"
    clip_file.write_bytes(b"audio")
    detection = create_detection(scientific_name=BLACKBIRD, clip_path=str(clip_file))

    response = admin_client.delete(f"/api/detections/{detection.id}/validate/")

    assert response.status_code == 204
    assert not clip_file.exists()
    assert not StoredDetection.objects.filter(pk=detection.id).exists()


def test_validate_detection_missing_pk_returns_404(admin_client: APIClient) -> None:
    assert admin_client.delete("/api/detections/999999/validate/").status_code == 404


def test_anonymous_can_delete_detection(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    # TODO(security): validate_detection has no permission class, so an anonymous
    # user can delete a detection and its clip file. This should require
    # IsAdminUser (see BACKEND-ANALYSIS.md). This test documents current behavior;
    # tighten the assertion to expect 403 once the endpoint is locked down.
    detection = create_detection(scientific_name=BLACKBIRD)

    response = api_client.delete(f"/api/detections/{detection.id}/validate/")

    assert response.status_code == 204
    assert not StoredDetection.objects.filter(pk=detection.id).exists()
