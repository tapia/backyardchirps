from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from backyardchirps.features.recording.audio.birdnet3.week import week_48_for


@pytest.mark.parametrize(
    ("date", "expected"),
    [
        (datetime(2023, 1, 1), 1),  # first day of a non-leap year
        (datetime(2023, 12, 31), 48),  # last day of a non-leap year
        (datetime(2024, 1, 1), 1),  # first day of a leap year
        (datetime(2024, 12, 31), 48),  # last day of a leap year
        (datetime(2024, 2, 29), 8),  # leap day
        (datetime(2023, 7, 1), 24),  # mid-year
    ],
)
def test_week_48_for_known_dates(date: datetime, expected: int) -> None:
    assert week_48_for(date) == expected


def test_week_48_for_stays_in_range_and_is_monotonic() -> None:
    day = datetime(2024, 1, 1, tzinfo=timezone.utc)
    previous = 0
    while day.year == 2024:
        week = week_48_for(day)
        assert 1 <= week <= 48
        assert week >= previous  # non-decreasing across the year
        previous = week
        day += timedelta(days=1)
