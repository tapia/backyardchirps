import sys
import types
from typing import Any

import pytest

from backyardchirps.features.recording.audio import acoustic_model

_BIRDNET_2_MODULE = "backyardchirps.features.recording.audio.birdnet2.analyzer"
_BIRDNET_3_MODULE = "backyardchirps.features.recording.audio.birdnet3.analyzer"


class _StubBirdNet2Analyzer:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class _StubBirdNet3Analyzer:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


@pytest.fixture(autouse=True)
def stub_analyzer_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    # The factory imports each analyzer inside its own branch, so putting stub modules in
    # sys.modules is enough to replace them. That keeps the real dependencies, meaning
    # birdnetlib, TensorFlow and onnxruntime, out of the tests, and at the same time
    # proves only the chosen model is ever imported.
    birdnet2_module = types.ModuleType(_BIRDNET_2_MODULE)
    birdnet2_module.BirdNet2Analyzer = _StubBirdNet2Analyzer  # type: ignore[attr-defined]
    birdnet3_module = types.ModuleType(_BIRDNET_3_MODULE)
    birdnet3_module.BirdNet3Analyzer = _StubBirdNet3Analyzer  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, _BIRDNET_2_MODULE, birdnet2_module)
    monkeypatch.setitem(sys.modules, _BIRDNET_3_MODULE, birdnet3_module)


def test_build_birdnet_3_passes_location_and_confidence() -> None:
    model = acoustic_model.build_acoustic_model("birdnet_3", latitude=40.0, longitude=-3.0, min_confidence=0.4)
    assert isinstance(model, _StubBirdNet3Analyzer)
    assert model.kwargs == {"latitude": 40.0, "longitude": -3.0, "min_confidence": 0.4}


def test_build_birdnet_2_maps_to_lat_lon_arguments() -> None:
    model = acoustic_model.build_acoustic_model("birdnet_2", latitude=40.0, longitude=-3.0, min_confidence=0.4)
    assert isinstance(model, _StubBirdNet2Analyzer)
    assert model.kwargs == {"lat": 40.0, "lon": -3.0, "min_confidence": 0.4}


def test_build_unknown_model_raises() -> None:
    with pytest.raises(ValueError, match="Unknown acoustic model"):
        acoustic_model.build_acoustic_model("perch_v2", latitude=0.0, longitude=0.0, min_confidence=0.4)


def test_build_birdnet_2_without_the_extra_says_how_to_fix_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    BirdNET 2 is an optional extra, so a station can be set to it without having it. The
    recorder then refuses to start, and the reason has to be actionable in a journal.
    """
    # None in sys.modules makes the import fail the way a missing birdnetlib would.
    monkeypatch.setitem(sys.modules, _BIRDNET_2_MODULE, None)

    with pytest.raises(RuntimeError, match="uv sync --extra birdnet2") as failure:
        acoustic_model.build_acoustic_model("birdnet_2", latitude=40.0, longitude=-3.0, min_confidence=0.4)

    assert "birdnet_3" in str(failure.value)


def test_birdnet_3_still_builds_without_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The whole point of the split: a station with no BirdNET 2 installed is a working one.
    """
    monkeypatch.setitem(sys.modules, _BIRDNET_2_MODULE, None)

    model = acoustic_model.build_acoustic_model("birdnet_3", latitude=40.0, longitude=-3.0, min_confidence=0.4)

    assert isinstance(model, _StubBirdNet3Analyzer)
