"""
Shared pytest fixtures, and the setup the test environment needs.

This module runs before pytest-django calls ``django.setup()``, which makes it the place
to set the environment variables the settings read as they are imported. In particular
``django_settings.py`` does ``os.environ["SECRET_KEY"]``, raising KeyError when it is
unset. Without this, no machine lacking a ``.env`` file could run the tests, CI included.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")

from datetime import datetime
from datetime import timezone
from typing import Callable

import numpy as np
import pytest

from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.species.entity import Species

# A handful of scientific names verified present in the bundled taxonomy JSON,
# used across tests that need a real, valid Species without hitting the database.
BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"
HOUSE_SPARROW = "Passer domesticus"


@pytest.fixture
def make_audio_clip() -> Callable[..., AudioClip]:
    """
    Builds an AudioClip of a given length from silence, in memory. No files and no audio
    hardware involved.
    """

    def _build(seconds: float = 3.0, sample_rate: int = 48000, recorded_at: datetime | None = None) -> AudioClip:
        sample_count = int(seconds * sample_rate)
        return AudioClip(
            recorded_at=recorded_at or datetime(2024, 6, 15, 8, 0, 0, tzinfo=timezone.utc),
            audio=np.zeros(sample_count, dtype=np.float32),
            sample_rate=sample_rate,
        )

    return _build


@pytest.fixture
def make_result() -> Callable[..., AnalysisResult]:
    """
    Builds an AnalysisResult at a given confidence, for a species the taxonomy really has.
    """

    def _build(scientific_name: str = BLACKBIRD, confidence: float = 0.8) -> AnalysisResult:
        return AnalysisResult(species=Species(scientific_name), confidence=confidence)

    return _build
