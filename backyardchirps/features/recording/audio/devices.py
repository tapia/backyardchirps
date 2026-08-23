import time
from collections.abc import Iterator

import numpy as np

# sounddevice is imported inside each function below rather than here. Importing it
# loads PortAudio, a native library, and the Linux wheel bundles none, so on a machine
# without libportaudio2 the import raises. This module is reachable from the URL
# configuration through the setup feature, so importing it here would stop the web
# process serving any page at all, over the two endpoints that need a microphone.
#
# The recorder imports sounddevice eagerly, which is right: a recorder that cannot
# open a microphone has nothing to do.

# How much sound one reading covers. Ten readings a second is faster than anyone can see
# a bar move, and each one costs a peak and a mean over 4800 numbers, which is nothing.
_READING_SECONDS = 0.1
_MEASURE_SAMPLE_RATE = 48000


class DeviceBusy(Exception):
    """
    The device is there but will not open. On a Pi this is almost always the recorder
    already holding it, since ALSA gives a capture device to one process at a time.
    """


def list_input_devices() -> list[tuple[int, str, int, float, bool]]:
    """
    Every device that can record, as (index, name, channels, sample rate, is default).

    Output-only devices are left out: half of what sounddevice reports on a Pi is HDMI
    and headphone jacks, and offering those as microphones only invites picking one.
    """
    import sounddevice as sd

    try:
        default_input = sd.default.device[0]
    except (TypeError, IndexError):
        default_input = None

    devices = []
    for index, device in enumerate(sd.query_devices()):
        channels = int(device["max_input_channels"])
        if channels < 1:
            continue
        devices.append(
            (
                index,
                str(device["name"]),
                channels,
                float(device["default_samplerate"]),
                index == default_input,
            )
        )
    return devices


def stream_input_levels(device: int | None, seconds: float) -> Iterator[tuple[float, float]]:
    """
    Listen on a device and yield (peak, rms) ten times a second, for up to `seconds`.

    The device stays open for the whole stream, and that is the point. Opening it once
    per reading leaves the microphone shut between them, so a clap that lands in one of
    the gaps is never heard: the meter then looks broken on a station whose microphone is
    fine. Holding the device also keeps two readings from racing each other for it.

    Raises DeviceBusy when the device will not open, or stops working part way through.
    On a Pi that is almost always the recorder holding it.

    The caller has to consume this to the end or close it. Whichever it does, the device
    is handed back.
    """
    import sounddevice as sd

    frames = int(_READING_SECONDS * _MEASURE_SAMPLE_RATE)
    deadline = time.monotonic() + seconds
    try:
        # The `with` is what hands the device back, and it does so when the caller stops
        # early too. That is the case that matters: the browser closing the connection is
        # the ordinary way this ends, and the recorder cannot start until the device is
        # free again.
        with sd.InputStream(
            samplerate=_MEASURE_SAMPLE_RATE,
            channels=1,
            device=device,
            dtype=np.float32,
            blocksize=frames,
        ) as stream:
            while time.monotonic() < deadline:
                block, _overflowed = stream.read(frames)
                samples = block[:, 0]
                yield float(np.max(np.abs(samples))), float(np.sqrt(np.mean(np.square(samples))))
    except Exception as exc:
        raise DeviceBusy(str(exc)) from exc
