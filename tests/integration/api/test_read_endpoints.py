from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Callable

import pytest
from rest_framework.test import APIClient

from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.features.species.taxonomy import taxonomy

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
BLACKBIRD_SLUG = "turdus-merula"
ROBIN = "Erithacus rubecula"


def test_species_list(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    # species_list defaults to the "high" confidence filter (0.9), so seed above it.
    create_detection(scientific_name=BLACKBIRD, confidence=0.95)

    response = api_client.get("/api/species/")

    assert response.status_code == 200
    species = response.data["species"]
    assert len(species) == 1
    assert species[0]["scientific_name"] == BLACKBIRD
    assert species[0]["slug"] == BLACKBIRD_SLUG
    assert species[0]["count_total"] == 1


def test_species_detail(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD)

    response = api_client.get(f"/api/species/{BLACKBIRD_SLUG}/")

    assert response.status_code == 200
    assert response.data["scientific_name"] == BLACKBIRD
    assert response.data["has_detections"] is True
    assert response.data["sounds"] == []  # xeno-canto stubbed


def test_species_detail_unknown_slug_404(api_client: APIClient) -> None:
    assert api_client.get("/api/species/not-a-real-slug/").status_code == 404


def test_species_recordings(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    recorded_at = datetime(2026, 1, 5, 8, 7, 31, tzinfo=timezone.utc)
    create_detection(
        scientific_name=BLACKBIRD, recorded_at=recorded_at, clip_path="/clips/a.wav", clip_duration_seconds=3.0
    )

    response = api_client.get(f"/api/species/{BLACKBIRD_SLUG}/recordings/")

    assert response.status_code == 200
    assert response.data["total"] == 1
    assert response.data["recordings"][0]["clip_url"].endswith("a.wav")
    # The frontend reads the capture time under this name.
    assert response.data["recordings"][0]["recorded_at"] == recorded_at


def test_dubious_detections(admin_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.PENDING)
    create_detection(scientific_name=BLACKBIRD, validation_status=ValidationStatus.AUTO_CONFIRMED)

    response = admin_client.get("/api/detections/dubious/")

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert admin_client.get("/api/detections/dubious/count/").data["count"] == 1


def test_dubious_detections_leaves_the_rest_of_the_recording_to_the_detail_endpoint(
    admin_client: APIClient, create_detection: Callable[..., Any]
) -> None:
    """
    The queue does not carry the other species of a recording. Only the review dialog
    needs them, and it opens one detection at a time, so the detail endpoint is where
    they belong.
    """
    recorded_at = datetime(2026, 1, 5, 8, 7, 31, tzinfo=timezone.utc)
    create_detection(scientific_name=ROBIN, recorded_at=recorded_at)
    create_detection(scientific_name=BLACKBIRD, recorded_at=recorded_at, validation_status=ValidationStatus.PENDING)

    queued = admin_client.get("/api/detections/dubious/").data["detections"][0]

    assert "also_identified" not in queued

    detail = admin_client.get(f"/api/detections/{queued['id']}/").data

    assert [entry["scientific_name"] for entry in detail["also_identified"]] == [ROBIN]


def test_detection_detail(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    recorded_at = datetime(2026, 1, 5, 8, 7, 31, tzinfo=timezone.utc)
    detection = create_detection(scientific_name=BLACKBIRD, recorded_at=recorded_at)

    response = api_client.get(f"/api/detections/{detection.id}/")

    assert response.status_code == 200
    assert response.data["id"] == detection.id
    assert response.data["species"]["scientific_name"] == BLACKBIRD
    # The frontend reads the capture time under this name.
    assert response.data["recorded_at"] == recorded_at
    # An auto-confirmed detection was never overruled and, in this fixture, carries
    # no analysis metadata.
    assert response.data["reviewed_by_human"] is False
    assert response.data["original_detection"] is None
    assert response.data["analysis_time_ms"] is None
    assert response.data["analysis_candidates"] == []


def test_detection_detail_exposes_analysis_metadata(
    api_client: APIClient, create_detection: Callable[..., Any]
) -> None:
    detection = create_detection(
        scientific_name=BLACKBIRD,
        analysis_time_ms=175,
        analysis_candidates=[
            {"label": BLACKBIRD, "confidence": 0.8},
            {"label": "Engine", "confidence": 0.2},
        ],
    )

    response = api_client.get(f"/api/detections/{detection.id}/")

    assert response.status_code == 200
    assert response.data["analysis_time_ms"] == 175
    candidates = response.data["analysis_candidates"]
    # The known species resolves to a slug and common name; the non-bird token
    # keeps only its raw label.
    assert candidates[0]["scientific_name"] == BLACKBIRD
    assert candidates[0]["slug"] is not None
    assert candidates[1]["label"] == "Engine"
    assert candidates[1]["slug"] is None


def test_detections_list(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    older = create_detection(recorded_at=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc), analysis_time_ms=90)
    newer = create_detection(
        recorded_at=datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc),
        confidence=0.82,
        analysis_time_ms=140,
        analysis_candidates=[
            {"label": BLACKBIRD, "confidence": 0.82},
            {"label": "Engine", "confidence": 0.2},
        ],
    )

    response = api_client.get("/api/detections/")

    assert response.status_code == 200
    assert response.data["total"] == 2
    entries = response.data["detections"]
    # Newest first.
    assert [entry["id"] for entry in entries] == [newer.id, older.id]

    newest = entries[0]
    assert newest["analysis_time_ms"] == 140
    assert newest["confidence"] == 0.82
    assert newest["species"]["scientific_name"] == BLACKBIRD
    # The frontend reads the capture time under this name.
    assert newest["recorded_at"] == datetime(2026, 1, 2, 8, 0, tzinfo=timezone.utc)
    # The full BirdNET list: a resolved species with a common name, then the
    # non-bird token keeping only its raw label.
    assert newest["candidates"][0]["scientific_name"] == BLACKBIRD
    assert newest["candidates"][0]["confidence"] == 0.82
    assert newest["candidates"][1]["label"] == "Engine"
    assert newest["candidates"][1]["slug"] is None

    # A detection with no stored candidates comes back with an empty list.
    assert entries[1]["candidates"] == []


def test_detections_list_falls_back_to_scientific_name(
    api_client: APIClient, create_detection: Callable[..., Any]
) -> None:
    # A stored detection whose species is no longer in the taxonomy is still
    # listed, showing its scientific name with no slug or common name.
    create_detection(scientific_name="Gone extinctus")

    response = api_client.get("/api/detections/")

    assert response.status_code == 200
    assert response.data["total"] == 1
    entry = response.data["detections"][0]
    assert entry["species"]["scientific_name"] == "Gone extinctus"
    assert entry["species"]["slug"] is None
    assert entry["species"]["common_name"] is None


def test_detections_list_filters_by_species(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    blackbird = create_detection(scientific_name=BLACKBIRD)
    create_detection(scientific_name=ROBIN)

    response = api_client.get("/api/detections/", {"species": BLACKBIRD})

    assert response.status_code == 200
    assert response.data["total"] == 1
    assert [entry["id"] for entry in response.data["detections"]] == [blackbird.id]


def test_detections_list_unknown_species_matches_nothing(
    api_client: APIClient, create_detection: Callable[..., Any]
) -> None:
    create_detection(scientific_name=BLACKBIRD)

    response = api_client.get("/api/detections/", {"species": "Gone extinctus"})

    assert response.status_code == 200
    assert response.data["total"] == 0
    assert response.data["detections"] == []


def test_detections_list_filters_by_date_range(api_client: APIClient, create_detection: Callable[..., Any]) -> None:
    create_detection(recorded_at=datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc))
    in_range = create_detection(recorded_at=datetime(2026, 1, 5, 8, 0, tzinfo=timezone.utc))
    create_detection(recorded_at=datetime(2026, 1, 10, 8, 0, tzinfo=timezone.utc))

    response = api_client.get(
        "/api/detections/",
        {"start": "2026-01-03T00:00:00", "end": "2026-01-06T23:59:59"},
    )

    assert response.status_code == 200
    assert response.data["total"] == 1
    assert [entry["id"] for entry in response.data["detections"]] == [in_range.id]


def test_detections_list_excludes_blacklisted(
    api_client: APIClient, create_detection: Callable[..., Any], create_override: Callable[..., Any]
) -> None:
    create_detection(scientific_name=BLACKBIRD)
    create_override(scientific_name=BLACKBIRD, blacklisted=True)

    response = api_client.get("/api/detections/")

    assert response.status_code == 200
    assert response.data["total"] == 0
    assert response.data["detections"] == []


def test_current_weather_null_shaped_without_location(api_client: APIClient) -> None:
    # No lat/lon configured (test default), so the reading is null-shaped.
    response = api_client.get("/api/weather/current/")

    assert response.status_code == 200
    assert response.data["temperature"] is None
    assert "local_time" in response.data


def test_taxonomy_search(api_client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # Scoped to a station's own species, which is what the endpoint does in practice.
    # Against the whole taxonomy this asserts nothing useful: there are enough Turdus
    # species worldwide that merula falls past the result limit on alphabetical order.
    monkeypatch.setattr(taxonomy, "_local_species", {BLACKBIRD, ROBIN})

    response = api_client.get("/api/taxonomy/search/?q=turdus")

    assert response.status_code == 200
    names = [entry["scientific_name"] for entry in response.data["species"]]
    assert names == [BLACKBIRD]


def test_taxonomy_search_short_query_returns_empty(api_client: APIClient) -> None:
    assert api_client.get("/api/taxonomy/search/?q=t").data["species"] == []
