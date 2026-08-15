from pathlib import Path

import pytest

from backyardchirps.features.recording import maintenance

_MODEL_SIZE = 16
_LABELS_SIZE = 8


class _FakeDownloads:
    """
    Stands in for the GitHub release, writing a file of the published size instead of
    fetching one. Records which URLs it was asked for.
    """

    def __init__(self) -> None:
        self.urls_seen: list[str] = []

    def download_file(self, url: str, destination: Path) -> None:
        self.urls_seen.append(url)
        size = _MODEL_SIZE if url == maintenance.github.GEOMODEL_MODEL_URL else _LABELS_SIZE
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"\0" * size)


@pytest.fixture
def downloads(monkeypatch: pytest.MonkeyPatch) -> _FakeDownloads:
    """
    Shrink the published sizes to something a test can write, and serve the files from
    memory rather than from the network.
    """
    fake = _FakeDownloads()
    monkeypatch.setattr(maintenance.github, "GEOMODEL_MODEL_SIZE", _MODEL_SIZE)
    monkeypatch.setattr(maintenance.github, "GEOMODEL_LABELS_SIZE", _LABELS_SIZE)
    monkeypatch.setattr(maintenance.github, "download_file", fake.download_file)
    return fake


def test_downloads_both_files_when_neither_is_there(tmp_path: Path, downloads: _FakeDownloads) -> None:
    written = maintenance.refresh_geomodel(
        model_destination=tmp_path / "geomodel.onnx",
        labels_destination=tmp_path / "geomodel_labels.txt",
    )

    assert written == ["geomodel.onnx", "geomodel_labels.txt"]
    assert downloads.urls_seen == [
        maintenance.github.GEOMODEL_MODEL_URL,
        maintenance.github.GEOMODEL_LABELS_URL,
    ]


def test_downloads_nothing_when_both_files_have_the_published_size(tmp_path: Path, downloads: _FakeDownloads) -> None:
    model = tmp_path / "geomodel.onnx"
    labels = tmp_path / "geomodel_labels.txt"
    model.write_bytes(b"\0" * _MODEL_SIZE)
    labels.write_bytes(b"\0" * _LABELS_SIZE)

    assert maintenance.refresh_geomodel(model_destination=model, labels_destination=labels) == []
    assert downloads.urls_seen == []


def test_replaces_a_file_of_a_different_size(tmp_path: Path, downloads: _FakeDownloads) -> None:
    """
    This is the upgrade path: a station carrying an earlier GeoModel has files of
    another size, and only those are fetched again.
    """
    model = tmp_path / "geomodel.onnx"
    labels = tmp_path / "geomodel_labels.txt"
    model.write_bytes(b"an earlier model of another size")
    labels.write_bytes(b"\0" * _LABELS_SIZE)

    written = maintenance.refresh_geomodel(model_destination=model, labels_destination=labels)

    assert written == ["geomodel.onnx"]
    assert downloads.urls_seen == [maintenance.github.GEOMODEL_MODEL_URL]
    assert model.stat().st_size == _MODEL_SIZE
