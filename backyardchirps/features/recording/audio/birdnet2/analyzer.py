import logging

from birdnetlib import Recording
from birdnetlib.analyzer import Analyzer as BirdNetAnalyzer

from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.detection import RAW_CANDIDATE_FLOOR
from backyardchirps.features.recording.audio.detection import Analysis
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import RawCandidate
from backyardchirps.features.species.entity import Species

logger = logging.getLogger(__name__)


class BirdNet2Analyzer:
    """
    The BirdNET 2 model, through birdnetlib. It filters by location itself, using the
    lat/lon given to Recording, so there is no separate range model as in BirdNET 3.
    """

    def __init__(self, lat: float, lon: float, min_confidence: float, overlap: float = 0.0) -> None:
        self._model = BirdNetAnalyzer()
        self._lat = lat
        self._lon = lon
        self._min_confidence = min_confidence
        self._overlap = overlap

    def analyze(self, clip: AudioClip) -> Analysis:
        raw_floor = min(RAW_CANDIDATE_FLOOR, self._min_confidence)
        with clip.as_wav() as wav_path:
            recording = Recording(
                analyzer=self._model,
                path=str(wav_path),
                lat=self._lat,
                lon=self._lon,
                date=clip.recorded_at,
                min_conf=raw_floor,
                overlap=self._overlap,
            )
            recording.analyze()

        if recording.detections:
            logger.info("BirdNET raw results:")
            for detection in recording.detections:
                logger.info(f"   {detection['scientific_name']} ({detection['confidence']:.0%})")

        # recording.detections is already filtered by location. All of it goes into the
        # raw list, but only the entries our taxonomy knows and that clear the detection
        # floor become results.
        results = []
        raw_candidates = []
        for detection in recording.detections:
            raw_candidates.append(RawCandidate(label=detection["scientific_name"], confidence=detection["confidence"]))
            species = Species.from_scientific_name(detection["scientific_name"])
            if species is None:
                # The model and the taxonomy file are downloaded separately, so when
                # their versions drift apart BirdNET can return an unknown label.
                logger.warning("Skipping BirdNET label missing from taxonomy: %s", detection["scientific_name"])
                continue
            if detection["confidence"] >= self._min_confidence:
                results.append(AnalysisResult(species=species, confidence=detection["confidence"]))
        return Analysis(results=results, raw_candidates=raw_candidates)
