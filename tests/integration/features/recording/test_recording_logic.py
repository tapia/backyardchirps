from typing import Any
from typing import Callable

import pytest

from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.logic import discard_blacklisted
from backyardchirps.features.recording.logic import recorder_startup_settings
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.species.entity import Species

pytestmark = pytest.mark.django_db

BLACKBIRD = "Turdus merula"
ROBIN = "Erithacus rubecula"


def test_discard_blacklisted_drops_only_blacklisted_species(create_override: Callable[..., Any]) -> None:
    create_override(scientific_name=ROBIN, blacklisted=True)
    results = [
        AnalysisResult(species=Species(BLACKBIRD), confidence=0.8),
        AnalysisResult(species=Species(ROBIN), confidence=0.9),
    ]

    kept = discard_blacklisted(results)

    assert [result.species.scientific_name for result in kept] == [BLACKBIRD]


def test_discard_blacklisted_keeps_everything_when_nothing_is_blacklisted() -> None:
    results = [
        AnalysisResult(species=Species(BLACKBIRD), confidence=0.8),
        AnalysisResult(species=Species(ROBIN), confidence=0.9),
    ]

    kept = discard_blacklisted(results)

    assert [result.species.scientific_name for result in kept] == [BLACKBIRD, ROBIN]


def test_recorder_startup_settings_reads_what_the_recorder_is_built_from() -> None:
    Settings.set(SettingsKey.LOCATION_LAT, "40.4")
    Settings.set(SettingsKey.LOCATION_LON, "-3.7")
    Settings.set(SettingsKey.ANALYSIS_MIN_CONFIDENCE, "0.8")

    startup_settings = recorder_startup_settings()

    assert startup_settings.latitude == 40.4
    assert startup_settings.longitude == -3.7
    assert startup_settings.min_confidence == 0.8


def test_recorder_startup_settings_are_equal_until_one_of_them_changes() -> None:
    before = recorder_startup_settings()

    assert recorder_startup_settings() == before

    Settings.set(SettingsKey.ANALYSIS_MIN_CONFIDENCE, "0.55")

    assert recorder_startup_settings() != before


def test_a_setting_the_recorder_reads_per_request_is_not_watched() -> None:
    """
    Only what the recorder cannot re-read belongs in the comparison. Everything else it
    picks up on the next clip, and restarting for it would cost a gap in the recording
    for nothing.
    """
    before = recorder_startup_settings()

    Settings.set(SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE, "0.55")

    assert recorder_startup_settings() == before


def test_an_unset_coordinate_reads_the_same_as_a_stored_zero() -> None:
    before = recorder_startup_settings()

    Settings.set(SettingsKey.LOCATION_LAT, "0")

    assert recorder_startup_settings() == before
