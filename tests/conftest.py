"""
Shared pytest fixtures, and the part of the environment the tests can still pin.

pytest-django calls ``django.setup()`` from ``pytest_load_initial_conftests``, before any
conftest is imported, so by the time this module runs the settings have already been read.
Nothing set here can change a value that ``django_settings.py`` took from the environment
as it was imported: SECRET_KEY, DEBUG and BACKYARDCHIRPS_DATA_DIR are all decided before
this point, from the real environment or from the ``.env`` that ``load_dotenv`` picks up.

What this module can still pin is anything read later than settings import. The
credentials below are read by migration 0002 when the test database is built, which is
well after this runs.
"""

import os

# Blanked so that neither the developer's .env nor an exported shell variable reaches the
# tests. Migration 0002 copies whatever these hold into AppSetting rows as the test
# database is built, so without this the suite would run against a database holding real
# Telegram and API credentials, and row counts would differ from machine to machine.
os.environ["TELEGRAM_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = ""

from datetime import datetime
from datetime import timezone
from typing import Callable

import numpy as np
import pytest

from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.species.entity import Species

# A handful of scientific names the tracked taxonomy sample carries, used across tests
# that need a real, valid Species without hitting the database. tools/build_taxonomy_seed.py
# is what keeps them in the sample.
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
