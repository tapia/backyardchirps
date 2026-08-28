from dataclasses import dataclass


@dataclass(frozen=True)
class RecorderStartupSettings:
    """
    Everything the recorder is built from and cannot change afterwards: the microphone it
    opens, and the three values the analyzer is compiled with.

    The recorder takes a copy of this when it starts and compares it against the stored
    settings on every clip, which is how it notices a change it would otherwise never
    see. Nothing else it uses is cached, so nothing else belongs here.
    """

    audio_device: int | None
    latitude: float
    longitude: float
    min_confidence: float
