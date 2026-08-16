from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Callable
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from backyardchirps.features.analytics import queries as analytics_queries
from backyardchirps.features.analytics.queries import TimeGranularity
from backyardchirps.features.species.entity import Species

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"
HOUSE_SPARROW = "Passer domesticus"

_MADRID = ZoneInfo("Europe/Madrid")


def test_species_detections_by_hour_of_day_buckets_and_zero_fills(create_detection: Callable[..., Any]) -> None:
    # Detection hours are extracted in the project timezone (Europe/Madrid), so build
    # the timestamps in that zone to make the expected buckets unambiguous.
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 16, 9, 30, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 14, 0, tzinfo=_MADRID))

    hourly = analytics_queries.species_detections_by_hour_of_day(Species(BLACKBIRD), start=None, end=None)

    assert len(hourly) == 24  # continuous, zero-filled series
    assert hourly[0] == 0  # gaps filled with zero
    assert hourly[1] == 0
    assert hourly[2] == 0
    assert hourly[9] == 2
    assert hourly[14] == 1
    assert sum(hourly) == 3


def test_species_detections_by_hour_of_day_respects_min_confidence(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID), confidence=0.9)
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID), confidence=0.4)

    hourly = analytics_queries.species_detections_by_hour_of_day(
        Species(BLACKBIRD), start=None, end=None, min_confidence=0.8
    )

    assert hourly[9] == 1


# --- species_detections_over_time -------------------------------------------


def test_over_time_hourly_granularity_zero_filled(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 11, 0, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 11, 30, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 13, 0, tzinfo=_MADRID))

    rows, granularity = analytics_queries.species_detections_over_time(
        Species(BLACKBIRD),
        start=datetime(2024, 6, 15, 10, 0, tzinfo=_MADRID),
        end=datetime(2024, 6, 15, 14, 0, tzinfo=_MADRID),
    )

    assert granularity == TimeGranularity.HOUR
    assert [row["count"] for row in rows] == [0, 2, 0, 1, 0]  # hours 10..14, 11:xx grouped


def test_over_time_daily_granularity_zero_filled(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 2, 9, 0, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 2, 18, 0, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 4, 9, 0, tzinfo=_MADRID))

    rows, granularity = analytics_queries.species_detections_over_time(
        Species(BLACKBIRD),
        start=datetime(2024, 6, 1, tzinfo=_MADRID),
        end=datetime(2024, 6, 5, tzinfo=_MADRID),
    )

    assert granularity == TimeGranularity.DAY
    assert [row["count"] for row in rows] == [0, 2, 0, 1, 0]  # 06-01..06-05


def test_over_time_monthly_granularity_zero_filled(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 2, 10, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 2, 20, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 4, 10, tzinfo=_MADRID))

    rows, granularity = analytics_queries.species_detections_over_time(
        Species(BLACKBIRD),
        start=datetime(2024, 1, 1, tzinfo=_MADRID),
        end=datetime(2024, 6, 1, tzinfo=_MADRID),
    )

    assert granularity == TimeGranularity.MONTH
    assert [row["count"] for row in rows] == [0, 2, 0, 1, 0, 0]  # Jan..Jun


def test_over_time_unbounded_returns_only_populated_months(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 2, 10, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 2, 20, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 5, 10, tzinfo=_MADRID))

    rows, granularity = analytics_queries.species_detections_over_time(Species(BLACKBIRD), start=None, end=None)

    assert granularity == TimeGranularity.MONTH
    assert [row["count"] for row in rows] == [2, 1]  # only Feb and May, sorted, no gap-fill
    assert [row["day"] for row in rows] == sorted(row["day"] for row in rows)


# --- species_detections_by_date_and_hour (heatmap) --------------------------


def test_by_date_and_hour_daily(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 16, 9, 0, tzinfo=_MADRID))

    cells, x_labels, granularity = analytics_queries.species_detections_by_date_and_hour(
        Species(BLACKBIRD),
        start=datetime(2024, 6, 15, tzinfo=_MADRID),
        end=datetime(2024, 6, 17, tzinfo=_MADRID),
    )

    assert granularity == TimeGranularity.DAY
    assert x_labels == ["2024-06-15", "2024-06-16", "2024-06-17"]
    assert {"x": "2024-06-15", "y": 9, "v": 1} in cells
    assert {"x": "2024-06-16", "y": 9, "v": 1} in cells


def test_by_date_and_hour_unbounded_is_monthly(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID))

    cells, x_labels, granularity = analytics_queries.species_detections_by_date_and_hour(
        Species(BLACKBIRD), start=None, end=None
    )

    assert granularity == TimeGranularity.MONTH
    assert x_labels == sorted({cell["x"] for cell in cells})


# --- species_detections_by_day_yearly ---------------------------------------


def test_by_day_yearly_counts_recent_days_and_excludes_old(create_detection: Callable[..., Any]) -> None:
    now = timezone.now()
    create_detection(scientific_name=BLACKBIRD, recorded_at=now - timedelta(days=1))
    create_detection(scientific_name=BLACKBIRD, recorded_at=now - timedelta(days=1))
    create_detection(scientific_name=BLACKBIRD, recorded_at=now - timedelta(days=2))
    create_detection(scientific_name=BLACKBIRD, recorded_at=now - timedelta(days=400))  # older than a year

    by_day = analytics_queries.species_detections_by_day_yearly(Species(BLACKBIRD))

    assert len(by_day) == 2  # the 400-day-old detection is excluded
    assert sum(by_day.values()) == 3
    assert max(by_day.values()) == 2  # the two same-day detections


# --- detections_by_species_hourly -------------------------------------------


def test_detections_by_species_hourly_structure_and_blacklist(
    create_detection: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    recent = timezone.now() - timedelta(minutes=30)
    create_detection(scientific_name=BLACKBIRD, recorded_at=recent)
    create_detection(scientific_name=BLACKBIRD, recorded_at=recent)
    create_detection(scientific_name=ROBIN, recorded_at=recent)
    create_override(scientific_name=ROBIN, blacklisted=True)

    result = analytics_queries.detections_by_species_hourly()

    assert len(result) == 24
    assert sum(entry["count"] for entry in result) == 2  # robin excluded

    populated = [entry for entry in result if entry["count"] > 0]
    assert len(populated) == 1
    assert populated[0]["top_species"][0]["scientific_name"] == BLACKBIRD
    assert "image_url" in populated[0]["top_species"][0]
    assert populated[0]["species_counts"] == {BLACKBIRD: 2}


# --- species_by_hour_of_day --------------------------------------------------


def test_species_by_hour_of_day_buckets_and_zero_fills(create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 16, 9, 30, tzinfo=_MADRID))
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 14, 0, tzinfo=_MADRID))
    create_detection(scientific_name=ROBIN, recorded_at=datetime(2024, 6, 15, 6, 30, tzinfo=_MADRID))

    result = analytics_queries.species_by_hour_of_day([Species(BLACKBIRD), Species(ROBIN)], "en", None, None)

    entries = result["species"]
    assert [entry["scientific_name"] for entry in entries] == [BLACKBIRD, ROBIN]
    blackbird = entries[0]
    assert len(blackbird["hours"]) == 24  # continuous, zero-filled series
    assert blackbird["hours"][0] == 0
    assert blackbird["hours"][9] == 2  # 9:00 and 9:30 on different days share the bucket
    assert blackbird["hours"][14] == 1
    assert blackbird["total"] == 3
    assert blackbird["common_name"]
    assert "image_url" in blackbird
    assert entries[1]["hours"][6] == 1


def test_species_by_hour_of_day_keeps_requested_order(create_detection: Callable[..., Any]) -> None:
    recorded_at = datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID)
    create_detection(scientific_name=BLACKBIRD, recorded_at=recorded_at)
    create_detection(scientific_name=ROBIN, recorded_at=recorded_at)

    result = analytics_queries.species_by_hour_of_day([Species(ROBIN), Species(BLACKBIRD)], "en", None, None)

    assert [entry["scientific_name"] for entry in result["species"]] == [ROBIN, BLACKBIRD]


def test_species_by_hour_of_day_skips_blacklisted_and_undetected(
    create_detection: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    recorded_at = datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID)
    create_detection(scientific_name=BLACKBIRD, recorded_at=recorded_at)
    create_detection(scientific_name=ROBIN, recorded_at=recorded_at)
    create_override(scientific_name=ROBIN, blacklisted=True)

    requested = [Species(BLACKBIRD), Species(ROBIN), Species(HOUSE_SPARROW)]  # sparrow never detected
    result = analytics_queries.species_by_hour_of_day(requested, "en", None, None)

    assert [entry["scientific_name"] for entry in result["species"]] == [BLACKBIRD]


def test_species_by_hour_of_day_respects_min_confidence(create_detection: Callable[..., Any]) -> None:
    recorded_at = datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID)
    create_detection(scientific_name=BLACKBIRD, recorded_at=recorded_at, confidence=0.9)
    create_detection(scientific_name=BLACKBIRD, recorded_at=recorded_at, confidence=0.4)

    result = analytics_queries.species_by_hour_of_day([Species(BLACKBIRD)], "en", None, None, min_confidence=0.8)

    assert result["species"][0]["hours"][9] == 1
    assert result["species"][0]["total"] == 1


def test_species_by_hour_of_day_days_for_bounded_range(create_detection: Callable[..., Any]) -> None:
    start = datetime(2024, 6, 10, 0, 0, tzinfo=_MADRID)
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 11, 9, 0, tzinfo=_MADRID))

    full_weeks = analytics_queries.species_by_hour_of_day([Species(BLACKBIRD)], "en", start, start + timedelta(days=7))
    partial_days = analytics_queries.species_by_hour_of_day(
        [Species(BLACKBIRD)], "en", start, start + timedelta(days=2, hours=12)
    )

    assert full_weeks["days"] == 7
    assert partial_days["days"] == 3  # partial days round up


def test_species_by_hour_of_day_days_defaults_to_first_detection(create_detection: Callable[..., Any]) -> None:
    first_recorded_at = datetime(2024, 6, 10, 8, 0, tzinfo=_MADRID)
    create_detection(scientific_name=BLACKBIRD, recorded_at=first_recorded_at)

    result = analytics_queries.species_by_hour_of_day(
        [Species(BLACKBIRD)], "en", None, first_recorded_at + timedelta(days=4)
    )

    assert result["days"] == 4


def test_species_by_hour_of_day_empty_selection_returns_no_species_and_one_day() -> None:
    result = analytics_queries.species_by_hour_of_day([], "en", None, None)

    assert result == {"species": [], "days": 1}


# --- multi_species_timelines ------------------------------------------------


def test_multi_species_timelines_skips_blacklisted_and_undetected(
    create_detection: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID))
    create_detection(scientific_name=ROBIN, recorded_at=datetime(2024, 6, 15, 9, 0, tzinfo=_MADRID))
    create_override(scientific_name=ROBIN, blacklisted=True)

    requested = [Species(BLACKBIRD), Species(ROBIN), Species(HOUSE_SPARROW)]  # sparrow never detected
    series, _ = analytics_queries.multi_species_timelines(requested, lang="en", start=None, end=None)

    assert [entry["scientific_name"] for entry in series] == [BLACKBIRD]
    assert isinstance(series[0]["data"], list)
