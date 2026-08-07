import numpy as np

# sounddevice is imported inside each function below rather than here, the same way
# build_acoustic_model imports its analyzers inside their branches. Importing it loads
# PortAudio, a native library, and the Linux wheel bundles none, so on a machine
# without libportaudio2 the import raises. This module is reachable from the URL
# configuration through the setup feature, so importing it here would stop the web
# process serving any page at all, over the two endpoints that need a microphone.
#
# The recorder imports sounddevice eagerly, which is right: a recorder that cannot
# open a microphone has nothing to do.

# How long to listen for when measuring a level. Long enough to catch a syllable of
# speech or a passing car, short enough that the wizard's meter still feels live.
_MEASURE_SECONDS = 1.0
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


def measure_input_level(device: int | None) -> tuple[float, float]:
    """
    Listen briefly to a device and return (peak, rms) of what it heard.

    Raises DeviceBusy when the device cannot be opened, which the caller has to expect:
    the recorder is normally running and holding the microphone already.
    """
    import sounddevice as sd

    frames = int(_MEASURE_SECONDS * _MEASURE_SAMPLE_RATE)
    try:
        recording = sd.rec(
            frames,
            samplerate=_MEASURE_SAMPLE_RATE,
            channels=1,
            device=device,
            dtype=np.float32,
        )
        sd.wait()
    except Exception as exc:
        raise DeviceBusy(str(exc)) from exc

    samples = recording[:, 0]
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
    return peak, rms
