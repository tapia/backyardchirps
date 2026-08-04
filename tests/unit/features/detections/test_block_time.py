from datetime import datetime
from datetime import timezone

import pytest

from backyardchirps.features.detections.queries import get_block_time


@pytest.mark.parametrize(
    ("minute", "second", "expected_minute"),
    [
        (7, 22, 6),  # 08:07:22 -> 08:06:00
        (6, 0, 6),  # already on a boundary
        (5, 59, 3),
        (2, 59, 0),
        (0, 0, 0),
    ],
)
def test_get_block_time_buckets_into_three_minute_blocks(minute: int, second: int, expected_minute: int) -> None:
    # RECORDING["detection_time_buffer_in_minutes"] is 3.
    result = get_block_time(datetime(2024, 6, 15, 8, minute, second, tzinfo=timezone.utc))

    assert result == datetime(2024, 6, 15, 8, expected_minute, 0, tzinfo=timezone.utc)
