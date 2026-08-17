from datetime import datetime
from typing import Any
from typing import Callable
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
BLACKBIRD_SLUG = "turdus-merula"
ROBIN = "Erithacus rubecula"
ROBIN_SLUG = "erithacus-rubecula"

_UTC = ZoneInfo("UTC")


def test_species_hourly(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, confidence=0.95)

    response = api_client.get(f"/api/species/{BLACKBIRD_SLUG}/hourly/")

    assert response.status_code == 200
    assert len(response.data["hourly"]) == 24


def test_species_hourly_undetected_slug_404(api_client: APIClient) -> None:
    assert api_client.get(f"/api/species/{BLACKBIRD_SLUG}/hourly/").status_code == 404


def test_species_heatmap(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, confidence=0.95)

    response = api_client.get(f"/api/species/{BLACKBIRD_SLUG}/heatmap/")

    assert response.status_code == 200
    assert set(response.data) == {"heatmap", "x_labels", "granularity"}


def test_species_yearly(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, confidence=0.95)

    response = api_client.get(f"/api/species/{BLACKBIRD_SLUG}/yearly/")

    assert response.status_code == 200
    assert isinstance(response.data["daily"], dict)


def test_species_seasonality_is_null_when_stubbed(api_client: APIClient) -> None:
    # get_yearly_seasonality is stubbed to None by the autouse fixture.
    response = api_client.get(f"/api/species/{BLACKBIRD_SLUG}/seasonality/")

    assert response.status_code == 200
    assert response.data["timeline"] is None


def test_multi_species_timeline(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, confidence=0.95)

    response = api_client.get(f"/api/detections/timeline/?species={BLACKBIRD_SLUG}")

    assert response.status_code == 200
    assert "granularity" in response.data
    assert [entry["scientific_name"] for entry in response.data["series"]] == [BLACKBIRD]


def test_count_detections_by_species_hourly(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, confidence=0.95)

    response = api_client.get("/api/detections/hourly/")

    assert response.status_code == 200
    assert len(response.data["hours"]) == 24
    # No location configured, so no astronomy events.
    assert response.data["astro"] == {"events": []}


def test_detections_by_hour_of_day(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, confidence=0.95)

    response = api_client.get(f"/api/detections/by-hour-of-day/?species={BLACKBIRD_SLUG}")

    assert response.status_code == 200
    assert isinstance(response.data["days"], int)
    entry = response.data["species"][0]
    assert set(entry) == {"scientific_name", "common_name", "image_url", "total", "hours"}
    assert entry["scientific_name"] == BLACKBIRD
    assert len(entry["hours"]) == 24


def test_detections_by_hour_of_day_parses_params(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, recorded_at=datetime(2024, 6, 15, 9, 0, tzinfo=_UTC), confidence=0.4)
    create_detection(scientific_name=ROBIN, recorded_at=datetime(2024, 7, 15, 9, 0, tzinfo=_UTC), confidence=0.95)

    response = api_client.get(
        f"/api/detections/by-hour-of-day/?species={BLACKBIRD_SLUG}&species={ROBIN_SLUG}"
        "&start=2024-06-14T00:00:00Z&end=2024-06-16T00:00:00Z&min_confidence=low"
    )

    assert response.status_code == 200
    totals = {entry["scientific_name"]: entry["total"] for entry in response.data["species"]}
    # min_confidence=low keeps the blackbird's 0.4 detection; the window excludes
    # the July robin, so it stays a selected but empty row (like the violin).
    assert totals == {BLACKBIRD: 1, ROBIN: 0}
    assert response.data["days"] == 2
