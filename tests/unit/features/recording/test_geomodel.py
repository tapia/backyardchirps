from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from backyardchirps.features.recording.audio.birdnet3 import geomodel
from backyardchirps.features.species.entity import Species

# Tab-separated "taxon_id, scientific name, common name" rows, in output-class
# order. Row 2 is a name absent from the taxonomy, which GeoModel drops.
_LABELS = "\n".join(
    [
        "1\tTurdus merula\tCommon Blackbird",
        "2\tErithacus rubecula\tEuropean Robin",
        "3\tImaginarius nonexistentus\tNot A Real Species",
        "4\tPasser domesticus\tHouse Sparrow",
    ]
)


class _FakeSession:
    """
    An ONNX session that always returns the same scores, so the tests can check how
    GeoModel resolves labels and applies the threshold without needing a model file.
    """

    def __init__(self, scores: list[float]) -> None:
        self._scores = np.array([scores], dtype=np.float32)
        self.last_input: np.ndarray | None = None

    def get_inputs(self) -> list[Any]:
        return [SimpleNamespace(name="input")]

    def get_outputs(self) -> list[Any]:
        return [SimpleNamespace(name="output")]

    def run(self, output_names: list[str], feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
        self.last_input = feeds["input"]
        return [self._scores]


@pytest.fixture
def build_geomodel(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    def _build(scores: list[float]) -> tuple[geomodel.GeoModel, _FakeSession]:
        session = _FakeSession(scores)
        monkeypatch.setattr(geomodel.ort, "InferenceSession", lambda *args, **kwargs: session)
        labels_path = tmp_path / "geomodel_labels.txt"
        labels_path.write_text(_LABELS)
        model = geomodel.GeoModel(model_path=tmp_path / "geomodel.onnx", labels_path=labels_path)
        return model, session

    return _build


def test_labels_absent_from_taxonomy_are_dropped(build_geomodel) -> None:
    model, _ = build_geomodel([0.9, 0.9, 0.9, 0.9])
    # Row 2 never resolves to a taxonomy species.
    assert set(model._species_by_index.values()) == {
        Species("Turdus merula"),
        Species("Erithacus rubecula"),
        Species("Passer domesticus"),
    }


def test_allowed_species_keeps_only_scores_at_or_above_threshold(build_geomodel) -> None:
    model, session = build_geomodel([0.5, 0.01, 0.9, 0.2])
    allowed = model.allowed_species(latitude=40.0, longitude=-3.0, week_48=24, threshold=0.03)
    # 0.5 (Blackbird) and 0.2 (House Sparrow) clear 0.03; 0.01 (Robin) does not;
    # 0.9 belongs to the dropped row absent from the taxonomy.
    assert allowed == {Species("Turdus merula"), Species("Passer domesticus")}
    # The raw [lat, lon, week] triple is passed through unchanged.
    assert session.last_input is not None
    np.testing.assert_array_equal(session.last_input, np.array([[40.0, -3.0, 24.0]], dtype=np.float32))


def test_allowed_species_empty_when_all_below_threshold(build_geomodel) -> None:
    model, _ = build_geomodel([0.5, 0.01, 0.9, 0.2])
    assert model.allowed_species(latitude=40.0, longitude=-3.0, week_48=24, threshold=0.6) == set()
