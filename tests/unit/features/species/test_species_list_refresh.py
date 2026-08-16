from pathlib import Path
from typing import Any

import numpy as np
import pytest

from backyardchirps.features.species import maintenance
from backyardchirps.features.species.entity import Species

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"
SPARROW = "Passer domesticus"


class _FakeGeoModel:
    """
    Stands in for the ONNX model, so the tests can drive what is plausible in each week
    without a model file. Records the weeks it was asked about.

    Scores come back as an array with one column per species, which is the shape that
    matters: the caller keeps the highest score it has seen and resolves names once at the
    end, rather than asking for a set of species on every run.
    """

    def __init__(self, species_by_week: dict[int, set[str]]) -> None:
        self._species_by_week = species_by_week
        self._names = sorted({name for names in species_by_week.values() for name in names})
        self.weeks_seen: list[int] = []
        self.threshold_seen: float | None = None

    def occurrence_scores(self, latitude: float, longitude: float, week_48: int) -> np.ndarray:
        self.weeks_seen.append(week_48)
        present = self._species_by_week.get(week_48, set())
        return np.array([1.0 if name in present else 0.0 for name in self._names], dtype=np.float32)

    def species_above(self, scores: np.ndarray, threshold: float) -> set[Species]:
        self.threshold_seen = threshold
        return {Species(name) for name, score in zip(self._names, scores, strict=True) if score >= threshold}


class _FakeGeoModelByPlace:
    """
    The same, for the cases where what matters is where the model was asked about rather
    than when. Every week gives the same answer at a given longitude.
    """

    def __init__(self, species_by_longitude: dict[float, set[str]]) -> None:
        self._species_by_longitude = species_by_longitude
        self._names = sorted({name for names in species_by_longitude.values() for name in names})
        self.longitudes_seen: set[float] = set()

    def occurrence_scores(self, latitude: float, longitude: float, week_48: int) -> np.ndarray:
        self.longitudes_seen.add(longitude)
        present = self._species_by_longitude.get(longitude, set())
        return np.array([1.0 if name in present else 0.0 for name in self._names], dtype=np.float32)

    def species_above(self, scores: np.ndarray, threshold: float) -> set[Species]:
        return {Species(name) for name, score in zip(self._names, scores, strict=True) if score >= threshold}


@pytest.fixture
def geomodel_files(tmp_path: Path, settings: Any) -> Path:
    """
    Point the GeoModel settings at files that exist, so refresh_species_list gets past
    its "not downloaded yet" guard. Their contents never matter: the model is faked.
    """
    model = tmp_path / "geomodel.onnx"
    labels = tmp_path / "geomodel_labels.txt"
    model.write_bytes(b"not a real model")
    labels.write_text("unused")
    settings.GEOMODEL_MODEL_FILE = model
    settings.GEOMODEL_LABELS_FILE = labels
    return tmp_path


@pytest.fixture
def species_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    destination = tmp_path / "species" / "species_birdnet.txt"
    monkeypatch.setattr(maintenance, "_SPECIES_FILE", destination)
    return destination


def _install_fake(monkeypatch: pytest.MonkeyPatch, fake: _FakeGeoModel) -> None:
    monkeypatch.setattr(maintenance, "GeoModel", lambda model_path, labels_path: fake)


def test_writes_the_union_of_every_week(
    monkeypatch: pytest.MonkeyPatch, geomodel_files: Path, species_file: Path
) -> None:
    """
    A summer visitor and a winter one both belong on the list, so the year is walked week
    by week and the results merged.
    """
    fake = _FakeGeoModel({3: {BLACKBIRD}, 20: {ROBIN, BLACKBIRD}, 44: {SPARROW}})
    _install_fake(monkeypatch, fake)

    maintenance.refresh_species_list(41.0, -3.7)

    written = [line for line in species_file.read_text().splitlines() if not line.startswith("#")]
    assert written == sorted([BLACKBIRD, ROBIN, SPARROW])


def test_asks_about_all_48_weeks(monkeypatch: pytest.MonkeyPatch, geomodel_files: Path, species_file: Path) -> None:
    fake = _FakeGeoModel({})
    _install_fake(monkeypatch, fake)

    maintenance.refresh_species_list(41.0, -3.7)

    assert fake.weeks_seen == list(range(1, 49))


def test_uses_a_lower_threshold_than_the_detection_filter(
    monkeypatch: pytest.MonkeyPatch, geomodel_files: Path, species_file: Path, settings: Any
) -> None:
    """
    An occasional visitor should still count as local, or it gets reported as rare every
    time it turns up.
    """
    fake = _FakeGeoModel({})
    _install_fake(monkeypatch, fake)

    maintenance.refresh_species_list(41.0, -3.7)

    assert fake.threshold_seen is not None
    assert fake.threshold_seen < settings.BIRDNET_3["geomodel_threshold"]


def test_the_header_records_no_coordinates(
    monkeypatch: pytest.MonkeyPatch, geomodel_files: Path, species_file: Path
) -> None:
    """
    The station's exact position is not provenance worth keeping in a file that has been
    committed to the repository before now.
    """
    _install_fake(monkeypatch, _FakeGeoModel({1: {BLACKBIRD}}))

    maintenance.refresh_species_list(41.01594, -3.675327)

    assert "41.01" not in species_file.read_text()
    assert "3.675" not in species_file.read_text()


def test_a_grid_of_points_gets_every_species_at_any_of_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    What a region pack is built from. A bird living at one edge of a box and not at the
    other still belongs to the box, or the pack ships without its raster and the station
    that can hear it has no seasonality chart.
    """
    fake = _FakeGeoModelByPlace({-10.0: {BLACKBIRD}, 4.5: {ROBIN, BLACKBIRD}})
    _install_fake(monkeypatch, fake)

    names = maintenance.plausible_species_names_over([(40.0, -10.0), (40.0, 4.5)])

    assert names == sorted([BLACKBIRD, ROBIN])
    assert fake.longitudes_seen == {-10.0, 4.5}


def test_one_point_is_the_station_asking_about_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    A station and the pack builder go through the same call, so the two can never disagree
    about what counts as plausible.
    """
    _install_fake(monkeypatch, _FakeGeoModelByPlace({-3.7: {SPARROW}, 4.5: {ROBIN}}))

    assert maintenance.plausible_species_names(41.0, -3.7) == [SPARROW]


def test_no_points_is_an_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake(monkeypatch, _FakeGeoModelByPlace({-3.7: {SPARROW}}))

    assert maintenance.plausible_species_names_over([]) == []


def test_does_nothing_when_geomodel_is_not_downloaded(
    monkeypatch: pytest.MonkeyPatch, species_file: Path, settings: Any, tmp_path: Path
) -> None:
    """
    A station that has not fetched the model yet keeps whatever list it had, rather than
    crashing the daily timer.
    """
    settings.GEOMODEL_MODEL_FILE = tmp_path / "absent.onnx"
    settings.GEOMODEL_LABELS_FILE = tmp_path / "absent.txt"

    maintenance.refresh_species_list(41.0, -3.7)

    assert not species_file.exists()
