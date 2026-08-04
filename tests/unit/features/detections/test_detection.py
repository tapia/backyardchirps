from datetime import datetime
from datetime import timezone

import pytest

from backyardchirps.features.detections.entity import Detection
from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.features.species.entity import Species


def _detection(status: ValidationStatus) -> Detection:
    return Detection(
        id=1,
        species=Species("Turdus merula"),
        recorded_at=datetime(2024, 6, 15, 8, 0, 0, tzinfo=timezone.utc),
        confidence=0.8,
        clip_path=None,
        clip_duration_seconds=None,
        validation_status=status,
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ValidationStatus.PENDING, True),
        (ValidationStatus.AUTO_CONFIRMED, False),
        (ValidationStatus.HUMAN_CONFIRMED, False),
    ],
)
def test_is_pending_validation(status: ValidationStatus, expected: bool) -> None:
    assert _detection(status).is_pending_validation() is expected
