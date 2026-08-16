from backyardchirps.features.detections import queries as detection_queries
from backyardchirps.features.detections.entity import Detection
from backyardchirps.features.overrides import queries as override_queries
from backyardchirps.features.recording.audio.consistency_filter import ConfirmedDetection
from backyardchirps.features.recording.audio.detection import AnalysisResult


def process_confirmed_detection(confirmed: ConfirmedDetection) -> Detection | None:
    """
    Save one confirmed detection, along with how long the analysis took and everything
    the model heard in the clip.

    Returns None when a record already exists and is at least as confident, as there is
    then nothing to update.
    """
    return detection_queries.upsert(
        confirmed.clip,
        confirmed.result,
        analysis_time_ms=confirmed.analysis_time_ms,
        raw_candidates=confirmed.raw_candidates,
    )


def discard_blacklisted(analysis_results: list[AnalysisResult]) -> list[AnalysisResult]:
    """
    Drop blacklisted species before they reach the consistency window or the database.
    The other species BirdNET heard in the same clip carry on as normal.
    """
    blacklisted = override_queries.blacklisted_species()
    return [result for result in analysis_results if result.species not in blacklisted]


def discard_non_birds(analysis_results: list[AnalysisResult]) -> list[AnalysisResult]:
    """
    BirdNET's taxonomy also covers insects, mammals, amphibians and reptiles, and none
    of those should become a detection. The caller still keeps the full raw candidate
    list for the record.
    """
    return [result for result in analysis_results if result.species.is_bird()]
