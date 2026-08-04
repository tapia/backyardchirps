import logging
import math
from collections.abc import Iterable
from pathlib import Path
from typing import cast

import librosa
import numpy as np
import onnxruntime as ort
from django.conf import settings

from backyardchirps.features.recording.audio.birdnet3.geomodel import GeoModel
from backyardchirps.features.recording.audio.birdnet3.week import week_48_for
from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.detection import RAW_CANDIDATE_FLOOR
from backyardchirps.features.recording.audio.detection import Analysis
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import RawCandidate
from backyardchirps.features.species.entity import Species

logger = logging.getLogger(__name__)

# Of the model's two outputs, this is the one with a score per species. The scores
# already come out of a sigmoid, between 0 and 1, so we use them as confidences as
# they are. Do not apply a sigmoid again: BirdNET's own tooling does it by default,
# and it would squeeze every score into the 0.5 to 0.73 range.
_PREDICTIONS_OUTPUT_NAME = "predictions"


class BirdNet3Analyzer:
    """
    Runs the BirdNET 3 acoustic model over a clip and returns the species it
    identifies at or above min_confidence.

    Everything runs through onnxruntime, including the GeoModel location filter, so
    neither the birdnet package nor TensorFlow is involved. The model file and its
    labels come from download_birdnet3_model.
    """

    def __init__(self, latitude: float, longitude: float, min_confidence: float) -> None:
        self._latitude = latitude
        self._longitude = longitude
        self._min_confidence = min_confidence
        self._geomodel_threshold: float = settings.BIRDNET_3["geomodel_threshold"]
        self._target_sample_rate: int = settings.BIRDNET_3["target_sample_rate"]
        self._window_samples: int = settings.BIRDNET_3["window_samples"]
        self._overlap_samples: int = int(
            (settings.RECORDING["clip_duration"] - settings.RECORDING["step_duration"]) * self._target_sample_rate
        )
        self._session = ort.InferenceSession(str(settings.BIRDNET3_MODEL_FILE), providers=["CPUExecutionProvider"])
        self._species_by_index: dict[int, Species] = {}
        # Kept as raw text so the record can also list the non-bird labels, which
        # never turn into a Species.
        self._labels: list[str] = [
            line.strip() for line in Path(settings.BIRDNET3_LABELS_FILE).read_text().splitlines()
        ]
        self._load_labels(self._labels)
        # With no location configured there is nothing to filter by, and the model
        # runs against the whole world.
        self._geomodel: GeoModel | None = None
        if self._latitude and self._longitude:
            self._geomodel = GeoModel(
                model_path=Path(settings.GEOMODEL_MODEL_FILE),
                labels_path=Path(settings.GEOMODEL_LABELS_FILE),
            )
        self._allowed_species_by_week: dict[int, set[Species]] = {}

    def analyze(self, clip: AudioClip) -> Analysis:
        # A clip covers several windows, and a species only needs to be heard clearly
        # in one of them, so each species keeps its best score across the lot.
        per_class_best = self._run(self._to_windows(clip)).max(axis=0)
        return rank_candidates(
            per_class_best=per_class_best,
            labels=self._labels,
            species_by_index=self._species_by_index,
            allowed_species=self._allowed_species(clip),
            min_confidence=self._min_confidence,
        )

    def _allowed_species(self, clip: AudioClip) -> set[Species] | None:
        """
        GeoModel's plausible species in the week of the clip, or None when no location
        is configured. Cached per week, as the location cannot change while we run.
        """
        if self._geomodel is None:
            return None
        week_48 = week_48_for(clip.recorded_at)
        if week_48 not in self._allowed_species_by_week:
            self._allowed_species_by_week[week_48] = self._geomodel.allowed_species(
                self._latitude, self._longitude, week_48, self._geomodel_threshold
            )
        return self._allowed_species_by_week[week_48]

    def _load_labels(self, scientific_names: Iterable[str]) -> None:
        # One scientific name per line, in the model's class order: line N is class N.
        for class_index, scientific_name in enumerate(scientific_names):
            species = Species.from_scientific_name(scientific_name.strip())
            if species is None:
                # A non-bird label, or one our taxonomy does not know. Either way we
                # cannot report it as a detection.
                continue
            self._species_by_index[class_index] = species

    def _to_windows(self, clip: AudioClip) -> np.ndarray:
        audio = clip.samples
        if clip.sample_rate != self._target_sample_rate:
            audio = librosa.resample(audio, orig_sr=clip.sample_rate, target_sr=self._target_sample_rate)

        step = self._window_samples - self._overlap_samples
        if len(audio) <= self._window_samples:
            window_starts = [0]
        else:
            window_count = math.ceil((len(audio) - self._window_samples) / step) + 1
            window_starts = [index * step for index in range(window_count)]

        windows = np.zeros((len(window_starts), self._window_samples), dtype=np.float32)
        for row, start in enumerate(window_starts):
            segment = audio[start : start + self._window_samples]
            windows[row, : len(segment)] = segment
        return windows

    def _run(self, windows: np.ndarray) -> np.ndarray:
        input_name = self._session.get_inputs()[0].name
        outputs = self._session.run([_PREDICTIONS_OUTPUT_NAME], {input_name: windows})
        return cast(np.ndarray, outputs[0])


def rank_candidates(
    per_class_best: np.ndarray,
    labels: list[str],
    species_by_index: dict[int, Species],
    allowed_species: set[Species] | None,
    min_confidence: float,
) -> Analysis:
    """
    Turn the model's best score per species into an Analysis.

    There are two floors. Anything above the raw floor is kept as a candidate, but only
    scores that also clear min_confidence become detections, so the record still shows
    the weak guesses the rest of the app never sees. Scores are walked from high to low,
    so the first one under the raw floor ends the loop.

    GeoModel only knows birds, so the location filter drops a known species that is out
    of range and leaves the non-bird labels it cannot judge alone. Blacklisted species
    stay as well, being both real and in range.
    """
    raw_floor = min(RAW_CANDIDATE_FLOOR, min_confidence)
    ranked_indices = np.argsort(-per_class_best)
    results = []
    raw_candidates = []
    for class_index in ranked_indices:
        confidence = float(per_class_best[class_index])
        if confidence < raw_floor:
            break
        species = species_by_index.get(int(class_index))
        if species is not None and allowed_species is not None and species not in allowed_species:
            continue
        raw_candidates.append(RawCandidate(label=labels[int(class_index)], confidence=confidence))
        if confidence >= min_confidence and species is not None:
            results.append(AnalysisResult(species=species, confidence=confidence))
    return Analysis(results=results, raw_candidates=raw_candidates)
