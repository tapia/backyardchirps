from pathlib import Path

import pytest
from rest_framework.test import APIClient

import backyardchirps.settings as app_settings_module

pytestmark = pytest.mark.django_db


@pytest.fixture
def served_clip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """
    Write a clip into a temporary directory and point save_dir at it.

    The patch goes on the module attribute because features/detections/views.py reads
    `backyardchirps.settings.CLIPS` rather than django.conf.settings.
    """
    clips = tmp_path / "clips"
    clips.mkdir()
    clip_file = clips / "sample.wav"
    clip_file.write_bytes(b"0123456789")
    monkeypatch.setattr(app_settings_module, "CLIPS", {**app_settings_module.CLIPS, "save_dir": str(clips)})
    return clip_file


def test_serve_clip_full_file(api_client: APIClient, served_clip: Path) -> None:
    response = api_client.get("/api/clips/sample.wav")

    assert response.status_code == 200
    assert response["Content-Type"] == "audio/wav"
    assert response["Accept-Ranges"] == "bytes"
    assert b"".join(response.streaming_content) == b"0123456789"


def test_serve_clip_range_request(api_client: APIClient, served_clip: Path) -> None:
    response = api_client.get("/api/clips/sample.wav", HTTP_RANGE="bytes=0-3")

    assert response.status_code == 206
    assert response["Content-Range"] == "bytes 0-3/10"
    assert response.content == b"0123"


def test_serve_clip_missing_file_404(api_client: APIClient, served_clip: Path) -> None:
    assert api_client.get("/api/clips/does-not-exist.wav").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/species-data/badcategory/x.jpg",  # category not allowed
        "/species-data/images/x.txt",  # unsupported extension
        "/species-data/images/nonexistent-asset.jpg",  # missing file
    ],
)
def test_serve_species_asset_404s(api_client: APIClient, path: str) -> None:
    assert api_client.get(path).status_code == 404
