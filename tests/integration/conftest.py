"""
Fixtures shared by the integration tests, which use the real ORM and filesystem.

Tests may build ORM rows directly. The rule that only queries modules import models is
about production code, not about how a test arranges its data.
"""

from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any
from typing import Callable

import pytest
from rest_framework.test import APIClient

from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.integrations import region_packs
from backyardchirps.models.detected_species import DetectedSpecies
from backyardchirps.models.stored_detection import StoredDetection
from backyardchirps.models.stored_species_override import StoredSpeciesOverride

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"
HOUSE_SPARROW = "Passer domesticus"

_DEFAULT_RECORDED_AT = datetime(2024, 6, 15, 8, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def create_detected_species(db: None) -> Callable[..., DetectedSpecies]:
    def _create(scientific_name: str = BLACKBIRD) -> DetectedSpecies:
        detected_species, _ = DetectedSpecies.objects.get_or_create(scientific_name=scientific_name)
        return detected_species

    return _create


@pytest.fixture
def create_detection(db: None) -> Callable[..., StoredDetection]:
    def _create(
        scientific_name: str = BLACKBIRD,
        recorded_at: datetime | None = None,
        confidence: float = 0.8,
        validation_status: ValidationStatus = ValidationStatus.AUTO_CONFIRMED,
        clip_path: str | None = None,
        clip_duration_seconds: float | None = None,
        analysis_time_ms: int | None = None,
        analysis_candidates: list[dict] | None = None,
    ) -> StoredDetection:
        detected_species, _ = DetectedSpecies.objects.get_or_create(scientific_name=scientific_name)
        return StoredDetection.objects.create(
            species=detected_species,
            recorded_at=recorded_at or _DEFAULT_RECORDED_AT,
            confidence=confidence,
            validation_status=validation_status,
            clip_path=clip_path,
            clip_duration_seconds=clip_duration_seconds,
            analysis_time_ms=analysis_time_ms,
            analysis_candidates=analysis_candidates,
        )

    return _create


@pytest.fixture
def create_override(db: None) -> Callable[..., StoredSpeciesOverride]:
    def _create(
        scientific_name: str = BLACKBIRD,
        threshold: float | None = None,
        blacklisted: bool = False,
    ) -> StoredSpeciesOverride:
        detected_species, _ = DetectedSpecies.objects.get_or_create(scientific_name=scientific_name)
        return StoredSpeciesOverride.objects.create(
            species=detected_species,
            auto_confirm_threshold=threshold,
            blacklisted=blacklisted,
        )

    return _create


@pytest.fixture
def clips_dir(settings: Any, tmp_path: Path) -> Path:
    """
    Send saved clips to a temporary directory, so no test ever writes one into the repo.
    pytest-django's `settings` fixture puts the original back afterwards.
    """
    directory = tmp_path / "clips"
    directory.mkdir()
    settings.CLIPS = {**settings.CLIPS, "save_dir": str(directory)}
    return directory


@pytest.fixture
def api_client() -> APIClient:
    """
    An anonymous DRF test client.
    """
    return APIClient()


@pytest.fixture
def admin_client(db: None, django_user_model: Any) -> APIClient:
    """
    A DRF test client authenticated as a staff/superuser.
    """
    admin = django_user_model.objects.create_superuser(username="admin", email="admin@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user=admin)
    return client


@pytest.fixture
def auth_client(db: None, django_user_model: Any) -> APIClient:
    """
    A DRF test client authenticated as an ordinary (non-admin) user.
    """
    user = django_user_model.objects.create_user(username="user", email="user@example.com", password="pw")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture(autouse=True)
def no_packs_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The wizard's region pack step asks the region packs index which pack covers a station, and that is
    an HTTP call to another repository. No test is allowed to make it: a suite that needs
    the internet is a suite that fails on a train.

    An empty index is the honest default, since it is what every test that is not about
    region packs would see anyway. Tests about region packs replace this.
    """
    monkeypatch.setattr(region_packs, "fetch_index", lambda: [])
