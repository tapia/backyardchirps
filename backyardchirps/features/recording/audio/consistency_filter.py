from collections import deque
from dataclasses import dataclass
from dataclasses import field

from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import RawCandidate
from backyardchirps.features.species.entity import Species

_ClipDetections = dict[Species, float]


@dataclass
class _ClipEntry:
    """
    One clip's place in the window. It also keeps the analysis time and the raw
    candidates, so that a confirmed detection can report how long the analysis took
    and everything the model heard.
    """

    clip: AudioClip
    detections: _ClipDetections
    raw_candidates: list[RawCandidate]
    analysis_time_ms: int


@dataclass(frozen=True)
class ConfirmedDetection:
    """
    A confirmed detection: the audio to save, the best analysis result, and the raw
    output of the clip where the species scored highest.
    """

    clip: AudioClip
    result: AnalysisResult
    analysis_time_ms: int
    raw_candidates: list[RawCandidate] = field(default_factory=list)


class ConsistencyFilter:
    """
    Drops dubious detections. To pass, a species must either appear in at least
    "min_detections" of the last "window_size" clips, or reach "bypass_confidence" in a
    single clip.

    A species confirmed by repetition gets the whole window joined into one AudioClip,
    so the reviewer hears the bird calling from start to finish. A species confirmed by
    the bypass alone gets only the clip that triggered it, because the rest of the
    window is unrelated audio that would just distract the reviewer.

    Examples:

    Repetition case: species A detected in clips 1, 2, and 3:
      add(clip1, [65%])  # only one valid detection, not enough yet. Doesn't return anything
      add(clip2, [70%])  # 2 consecutive detections. Returns clips 1+2 (4.5 seconds long). Confidence: 70%
      add(clip3, [67%])  # 3 consecutive detections. Returns clips 1+2+3 (6 seconds long). Confidence: 70%

    Bypass case: species B detected at 85% in a single clip:
      add(clip1, [85%])  # single high-confidence hit, returns clip only (3 seconds long)
    """

    def __init__(
        self,
        window_size: int,
        min_detections: int,
        bypass_confidence: float,
        overlap_time: float,
    ) -> None:
        self._window_size = window_size
        self._min_detections = min_detections
        self._bypass_confidence = bypass_confidence
        self._overlap_time = overlap_time
        self._history: deque[_ClipEntry] = deque(maxlen=window_size)

    def add(
        self,
        clip: AudioClip,
        results: list[AnalysisResult],
        raw_candidates: list[RawCandidate] | None = None,
        analysis_time_ms: int = 0,
    ) -> list[ConfirmedDetection]:
        """
        Record results for the latest clip and return confirmed detections.

        Called once per clip. While a bird keeps singing the same species can be
        confirmed on several calls in a row.
        """
        detections = {result.species: result.confidence for result in results}

        self._history.append(
            _ClipEntry(
                clip=clip,
                detections=detections,
                raw_candidates=raw_candidates or [],
                analysis_time_ms=analysis_time_ms,
            )
        )

        return self._confirmed_results()

    def _confirmed_results(self) -> list[ConfirmedDetection]:
        appearances: dict[Species, int] = {}
        max_confidence: dict[Species, float] = {}

        for entry in self._history:
            for species, confidence in entry.detections.items():
                appearances[species] = appearances.get(species, 0) + 1
                max_confidence[species] = max(max_confidence.get(species, 0.0), confidence)

        confirmed = []
        for species, count in appearances.items():
            passes_repetition = count >= self._min_detections
            passes_bypass = max_confidence[species] >= self._bypass_confidence

            if not passes_repetition and not passes_bypass:
                continue

            # Take the raw output from the clip that scored highest, the same one whose
            # confidence the detection reports.
            best_entry = self._entry_with_highest_confidence(species)
            if best_entry is None:
                continue

            if passes_repetition:
                # The bird called across several clips, so merge the window and let the
                # reviewer hear the whole thing.
                audio_clip = AudioClip.merge([entry.clip for entry in self._history], self._overlap_time)
            else:
                # A single confident hit. Merging the window here would pull in audio
                # from around it, where a second bird may well be singing, and leave the
                # reviewer unsure which one was detected.
                audio_clip = best_entry.clip

            confirmed.append(
                ConfirmedDetection(
                    clip=audio_clip,
                    result=AnalysisResult(species=species, confidence=max_confidence[species]),
                    analysis_time_ms=best_entry.analysis_time_ms,
                    raw_candidates=best_entry.raw_candidates,
                )
            )

        return confirmed

    def _entry_with_highest_confidence(self, species: Species) -> _ClipEntry | None:
        best_entry: _ClipEntry | None = None
        best_confidence = 0.0
        for entry in self._history:
            confidence = entry.detections.get(species, 0.0)
            if confidence > best_confidence:
                best_entry = entry
                best_confidence = confidence
        return best_entry
