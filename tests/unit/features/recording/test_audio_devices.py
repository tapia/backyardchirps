from typing import Any

import numpy as np
import pytest

from backyardchirps.features.recording.audio import devices

_PI_DEVICES: list[dict[str, Any]] = [
    {"name": "USB Audio Device", "max_input_channels": 1, "default_samplerate": 48000.0},
    {"name": "bcm2835 Headphones", "max_input_channels": 0, "default_samplerate": 48000.0},
    {"name": "vc4-hdmi", "max_input_channels": 0, "default_samplerate": 48000.0},
    {"name": "Webcam Mic", "max_input_channels": 2, "default_samplerate": 44100.0},
]


@pytest.fixture
def stub_sounddevice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(devices.sd, "query_devices", lambda: _PI_DEVICES)
    monkeypatch.setattr(devices.sd, "default", type("_Default", (), {"device": (0, 1)})())


def test_only_devices_that_can_record_are_offered(stub_sounddevice: None) -> None:
    """
    Half of what a Pi reports is HDMI and headphone jacks. Offering those as microphones
    only invites picking one.
    """
    listed = devices.list_input_devices()

    assert [name for _, name, _, _, _ in listed] == ["USB Audio Device", "Webcam Mic"]


def test_the_index_survives_the_filtering(stub_sounddevice: None) -> None:
    """
    The index is what gets saved and handed back to sounddevice, so it has to stay the
    position in the full device list, not in the filtered one.
    """
    listed = devices.list_input_devices()

    assert [index for index, _, _, _, _ in listed] == [0, 3]


def test_the_system_default_is_marked(stub_sounddevice: None) -> None:
    listed = devices.list_input_devices()

    assert [is_default for _, _, _, _, is_default in listed] == [True, False]


def test_level_measures_peak_and_rms(monkeypatch: pytest.MonkeyPatch) -> None:
    samples = np.array([[0.0], [0.5], [-1.0], [0.5]], dtype=np.float32)
    monkeypatch.setattr(devices.sd, "rec", lambda *args, **kwargs: samples)
    monkeypatch.setattr(devices.sd, "wait", lambda: None)

    peak, rms = devices.measure_input_level(device=0)

    assert peak == 1.0
    # A loud click and a steady hum differ here, which is why both are reported.
    assert rms == pytest.approx(0.6123724)


def test_a_device_that_will_not_open_is_reported_as_busy(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The normal case on a running station: ALSA gives a capture device to one process at
    a time, and the recorder already has it.
    """

    def _raise(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Error opening InputStream: Device unavailable")

    monkeypatch.setattr(devices.sd, "rec", _raise)

    with pytest.raises(devices.DeviceBusy):
        devices.measure_input_level(device=0)
