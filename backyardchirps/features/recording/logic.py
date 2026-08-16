from backyardchirps.features.overrides import queries as override_queries
from backyardchirps.features.recording.audio.detection import AnalysisResult


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
