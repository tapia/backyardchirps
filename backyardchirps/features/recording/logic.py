from backyardchirps.features.overrides import queries as override_queries
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.entity import RecorderStartupSettings
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey


def discard_blacklisted(analysis_results: list[AnalysisResult]) -> list[AnalysisResult]:
    """
    Drop blacklisted species before they reach the consistency window or the database.
    The other species BirdNET heard in the same clip carry on as normal.

    This lives here rather than beside the other result filter in audio/ because it is
    the one that has to read the blacklist. Everything under audio/ works without a
    database, and that is worth keeping.
    """
    blacklisted = override_queries.blacklisted_species()
    return [result for result in analysis_results if result.species not in blacklisted]


def recorder_startup_settings() -> RecorderStartupSettings:
    """
    The settings a recorder starting right now would be built from.

    A running recorder compares its own copy against this to find out whether it is still
    the recorder the settings describe. The coordinates fall back to 0.0 here rather than
    at the call site, so an unset coordinate and a stored 0.0 do not read as a change.
    """
    return RecorderStartupSettings(
        audio_device=Settings.get(SettingsKey.AUDIO_DEVICE),
        latitude=Settings.get(SettingsKey.LOCATION_LAT) or 0.0,
        longitude=Settings.get(SettingsKey.LOCATION_LON) or 0.0,
        min_confidence=Settings.get(SettingsKey.ANALYSIS_MIN_CONFIDENCE),
    )
