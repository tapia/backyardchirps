from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from zoneinfo import ZoneInfo

import pytest

from backyardchirps.features.analytics.queries import TimeGranularity
from backyardchirps.features.analytics.queries import _complete_bounded_series
from backyardchirps.features.analytics.queries import _complete_month_series
from backyardchirps.features.analytics.queries import _date_axis_labels
from backyardchirps.features.analytics.queries import _month_labels
from backyardchirps.features.analytics.queries import _period_start
from backyardchirps.features.analytics.queries import _pick_granularity

_MADRID = ZoneInfo("Europe/Madrid")

_HOUR = 3600
_DAY = 24 * _HOUR


# --- _pick_granularity -------------------------------------------------------


@pytest.mark.parametrize(
    ("span_seconds", "expected"),
    [
        (48 * _HOUR, TimeGranularity.HOUR),  # exactly 48h -> hourly
        (48 * _HOUR + 1, TimeGranularity.DAY),  # just over 48h -> daily
        (90 * _DAY, TimeGranularity.DAY),  # exactly 90d -> daily
        (90 * _DAY + 1, TimeGranularity.MONTH),  # just over 90d -> monthly
    ],
)
def test_pick_granularity_thresholds(span_seconds: int, expected: TimeGranularity) -> None:
    end = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
    start = end - timedelta(seconds=span_seconds)
    granularity, _ = _pick_granularity(start, end)
    assert granularity == expected


def test_pick_granularity_without_start_is_monthly() -> None:
    granularity, _ = _pick_granularity(None, datetime(2024, 6, 15, tzinfo=timezone.utc))
    assert granularity == TimeGranularity.MONTH


# --- _period_start -----------------------------------------------------------


def test_period_start_hourly_truncates_to_hour() -> None:
    assert _period_start(datetime(2024, 6, 15, 14, 37, 22), use_hourly=True) == datetime(2024, 6, 15, 14, 0)


def test_period_start_daily_truncates_to_day() -> None:
    assert _period_start(datetime(2024, 6, 15, 14, 37, 22), use_hourly=False) == datetime(2024, 6, 15, 0, 0)


# --- _month_labels -----------------------------------------------------------


def test_month_labels_spans_year_boundary() -> None:
    assert _month_labels(date(2024, 11, 15), date(2025, 2, 3)) == [
        "2024-11-01",
        "2024-12-01",
        "2025-01-01",
        "2025-02-01",
    ]


def test_month_labels_single_month() -> None:
    assert _month_labels(date(2024, 6, 10), date(2024, 6, 20)) == ["2024-06-01"]


# --- _complete_month_series --------------------------------------------------


def test_complete_month_series_zero_fills_gaps() -> None:
    by_period = {datetime(2024, 6, 1): {"count": 5}}

    result = _complete_month_series(by_period, datetime(2024, 5, 15), datetime(2024, 7, 20))

    assert result == [
        {"day": "2024-05-01", "count": 0},
        {"day": "2024-06-01", "count": 5},
        {"day": "2024-07-01", "count": 0},
    ]


# --- _complete_bounded_series ------------------------------------------------


def test_complete_bounded_series_daily() -> None:
    by_period = {datetime(2024, 6, 16): {"count": 4}}

    result = _complete_bounded_series(by_period, datetime(2024, 6, 15, 10), datetime(2024, 6, 17, 5), use_hourly=False)

    assert [row["count"] for row in result] == [0, 4, 0]
    assert [row["day"] for row in result] == ["2024-06-15T00:00:00", "2024-06-16T00:00:00", "2024-06-17T00:00:00"]


def test_complete_bounded_series_hourly() -> None:
    by_period = {datetime(2024, 6, 15, 12): {"count": 2}}

    result = _complete_bounded_series(
        by_period, datetime(2024, 6, 15, 10, 30), datetime(2024, 6, 15, 13, 0), use_hourly=True
    )

    assert [row["count"] for row in result] == [0, 0, 2, 0]  # 10:00, 11:00, 12:00, 13:00
    assert len(result) == 4


# --- _date_axis_labels -------------------------------------------------------


def test_date_axis_labels_bounded_daily() -> None:
    start = datetime(2024, 6, 15, tzinfo=_MADRID)
    local_end = datetime(2024, 6, 17, tzinfo=_MADRID)

    assert _date_axis_labels(start, local_end, use_daily=True, cells=[]) == ["2024-06-15", "2024-06-16", "2024-06-17"]


def test_date_axis_labels_bounded_monthly() -> None:
    start = datetime(2024, 5, 10, tzinfo=_MADRID)
    local_end = datetime(2024, 7, 5, tzinfo=_MADRID)

    assert _date_axis_labels(start, local_end, use_daily=False, cells=[]) == ["2024-05-01", "2024-06-01", "2024-07-01"]


def test_date_axis_labels_unbounded_uses_sorted_distinct_cell_dates() -> None:
    cells = [{"x": "2024-06-16"}, {"x": "2024-06-15"}, {"x": "2024-06-16"}]

    assert _date_axis_labels(None, datetime(2024, 6, 20, tzinfo=_MADRID), use_daily=True, cells=cells) == [
        "2024-06-15",
        "2024-06-16",
    ]
