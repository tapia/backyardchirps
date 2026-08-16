import importlib
import sys
from types import ModuleType
from typing import Any
from typing import ClassVar

import numpy as np
import pytest

from backyardchirps.features.recording.audio import devices

_PI_DEVICES: list[dict[str, Any]] = [
    {"name": "USB Audio Device", "max_input_channels": 1, "default_samplerate": 48000.0},
    {"name": "bcm2835 Headphones", "max_input_channels": 0, "default_samplerate": 48000.0},
    {"name": "vc4-hdmi", "max_input_channels": 0, "default_samplerate": 48000.0},
    {"name": "Webcam Mic", "max_input_channels": 2, "default_samplerate": 44100.0},
]


class FakeInputStream:
    """
    A microphone that hands out the same block of samples every time it is read.

    Records whether it was closed, which is what the leak tests look at: a stream left
    open is a microphone the recorder cannot have back.
    """

    block: ClassVar["np.ndarray[Any, Any]"] = np.zeros((1, 1), dtype=np.float32)
    instances: ClassVar[list["FakeInputStream"]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.closed = False
        self.fail_next_read = False
        FakeInputStream.instances.append(self)

    def __enter__(self) -> "FakeInputStream":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def read(self, frames: int) -> tuple["np.ndarray[Any, Any]", bool]:
        if self.fail_next_read:
            raise RuntimeError("Error reading from InputStream: Device unavailable")
        return FakeInputStream.block, False

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_sounddevice(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """
    Stand in for sounddevice in sys.modules, which is where the functions under test
    import it from.

    Replacing the module rather than patching attributes on the real one is what lets
    this run at all on a machine with no PortAudio, which is every Linux box that has
    not installed libportaudio2, CI included.
    """
    FakeInputStream.block = np.zeros((1, 1), dtype=np.float32)
    FakeInputStream.instances = []
    module = ModuleType("sounddevice")
    module.query_devices = lambda: _PI_DEVICES  # type: ignore[attr-defined]
    module.default = type("_Default", (), {"device": (0, 1)})()  # type: ignore[attr-defined]
    module.InputStream = FakeInputStream  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sounddevice", module)
    return module


def test_only_devices_that_can_record_are_offered(fake_sounddevice: ModuleType) -> None:
    """
    Half of what a Pi reports is HDMI and headphone jacks. Offering those as microphones
    only invites picking one.
    """
    listed = devices.list_input_devices()

    assert [name for _, name, _, _, _ in listed] == ["USB Audio Device", "Webcam Mic"]


def test_the_index_survives_the_filtering(fake_sounddevice: ModuleType) -> None:
    """
    The index is what gets saved and handed back to sounddevice, so it has to stay the
    position in the full device list, not in the filtered one.
    """
    listed = devices.list_input_devices()

    assert [index for index, _, _, _, _ in listed] == [0, 3]


def test_the_system_default_is_marked(fake_sounddevice: ModuleType) -> None:
    listed = devices.list_input_devices()

    assert [is_default for _, _, _, _, is_default in listed] == [True, False]


def test_a_reading_carries_peak_and_rms(fake_sounddevice: ModuleType) -> None:
    FakeInputStream.block = np.array([[0.0], [0.5], [-1.0], [0.5]], dtype=np.float32)

    levels = devices.stream_input_levels(device=0, seconds=60)
    peak, rms = next(levels)
    levels.close()

    assert peak == 1.0
    # A loud click and a steady hum differ here, which is why both are reported.
    assert rms == pytest.approx(0.6123724)


def test_the_device_is_opened_once_for_the_whole_stream(fake_sounddevice: ModuleType) -> None:
    """
    What the stream exists for. Opening the device per reading left it shut in between,
    so a sound could fall in a gap and never show on the meter.
    """
    levels = devices.stream_input_levels(device=0, seconds=60)
    next(levels)
    next(levels)
    next(levels)
    levels.close()

    assert len(FakeInputStream.instances) == 1


def test_stopping_early_hands_the_device_back(fake_sounddevice: ModuleType) -> None:
    """
    The browser closing the connection is the ordinary way a stream ends, and the
    recorder cannot start until the device it leaves behind is closed.
    """
    levels = devices.stream_input_levels(device=0, seconds=60)
    next(levels)
    opened_stream = FakeInputStream.instances[-1]

    levels.close()

    assert opened_stream.closed


def test_the_stream_stops_at_its_cap(fake_sounddevice: ModuleType) -> None:
    """
    A tab left on the microphone step has to give the device back on its own.
    """
    assert list(devices.stream_input_levels(device=0, seconds=0)) == []
    assert FakeInputStream.instances[-1].closed


def test_a_device_that_will_not_open_is_reported_as_busy(fake_sounddevice: ModuleType) -> None:
    """
    The normal case on a running station: ALSA gives a capture device to one process at
    a time, and the recorder already has it.
    """

    def _raise(**kwargs: object) -> None:
        raise RuntimeError("Error opening InputStream: Device unavailable")

    fake_sounddevice.InputStream = _raise  # type: ignore[attr-defined]

    with pytest.raises(devices.DeviceBusy):
        next(devices.stream_input_levels(device=0, seconds=60))


def test_a_device_that_stops_working_is_reported_as_busy(fake_sounddevice: ModuleType) -> None:
    """
    A USB microphone unplugged half way through setup, which is a thing people do while
    working out which socket the thing is in.
    """
    levels = devices.stream_input_levels(device=0, seconds=60)
    next(levels)
    opened_stream = FakeInputStream.instances[-1]
    opened_stream.fail_next_read = True

    with pytest.raises(devices.DeviceBusy):
        next(levels)

    assert opened_stream.closed


def test_importing_the_module_does_not_load_portaudio() -> None:
    """
    The regression this file exists for. devices.py is reachable from the URL
    configuration through the setup feature, so importing it must not pull in
    sounddevice: that loads PortAudio, and a Linux box without libportaudio2 would
    then fail to serve any page at all.
    """
    sys.modules.pop("sounddevice", None)

    importlib.reload(devices)

    assert "sounddevice" not in sys.modules
