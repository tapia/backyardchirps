from typing import Protocol

from django.conf import settings

from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.detection import Analysis


class AcousticModel(Protocol):
    """
    The interface every acoustic model implements.
    """

    def analyze(self, clip: AudioClip) -> Analysis:
        """
        Both lists come back empty when the model hears nothing.
        """
        ...


def build_acoustic_model(
    model_key: str,
    latitude: float,
    longitude: float,
    min_confidence: float,
) -> AcousticModel:
    """
    Build the analyzer named by model_key, which comes from the ACTIVE_ACOUSTIC_MODEL
    setting. Both analyzers load their weights here, so a missing model file breaks the
    recorder at startup instead of on the first clip.

    The imports sit inside the branches on purpose, to load only what the chosen model
    needs: BirdNET 3 never pulls in birdnetlib or TensorFlow, BirdNET 2 never pulls in
    onnxruntime. BirdNET 2 is an optional extra, so it may not be installed at all.
    """
    if model_key == settings.BIRDNET_3["model_key"]:
        from backyardchirps.features.recording.audio.birdnet3.analyzer import BirdNet3Analyzer

        return BirdNet3Analyzer(latitude=latitude, longitude=longitude, min_confidence=min_confidence)
    if model_key == "birdnet_2":
        try:
            from backyardchirps.features.recording.audio.birdnet2.analyzer import BirdNet2Analyzer
        except ImportError as missing_birdnetlib:
            raise RuntimeError(
                "The active acoustic model is birdnet_2, but this install does not have it. "
                "Either set active_acoustic_model back to birdnet_3, or install BirdNET 2 with "
                "`uv sync --extra birdnet2` and restart the recorder."
            ) from missing_birdnetlib

        return BirdNet2Analyzer(lat=latitude, lon=longitude, min_confidence=min_confidence)
    raise ValueError(f"Unknown acoustic model: {model_key!r}")
