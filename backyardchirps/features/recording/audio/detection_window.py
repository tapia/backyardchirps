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
    candidates, so that a detection can report how long the analysis took and everything
    the model heard.
    """

    clip: AudioClip
    detections: _ClipDetections
    raw_candidates: list[RawCandidate]
    analysis_time_ms: int


@dataclass(frozen=True)
class RecordedDetection:
    """
    A detection and the audio to save with it: the best analysis result, and the raw
    output of the clip where the species scored highest.
    """

    clip: AudioClip
    result: AnalysisResult
    analysis_time_ms: int
    raw_candidates: list[RawCandidate] = field(default_factory=list)


class DetectionWindow:
    """
    Keeps the last few clips so that a detection can be given the audio it deserves.

    Everything BirdNET hears above the station's minimum confidence becomes a detection.
    That threshold is the only thing deciding what is worth recording, and this window
    decides nothing about it. What it decides is how much audio goes with each one.

    A species heard in "min_clips_to_merge" of the last "window_size" clips gets them
    joined into a single recording, so the reviewer hears the bird calling from start to
    finish. A species heard once keeps its own clip: merging the window around a single
    call would pull in audio from around it, where a second bird may well be singing, and
    leave the reviewer unsure which one was detected.

    Examples, with a window of 3 clips merged from 2:

    A bird calling across several clips:
      add(clip1, [65%])  # heard once, returns clip 1 alone (3 seconds). Confidence: 65%
      add(clip2, [70%])  # heard twice, returns clips 1+2 (4.5 seconds). Confidence: 70%
      add(clip3, [67%])  # heard three times, returns clips 1+2+3 (6 seconds). Confidence: 70%

    A single call that is over before the next clip starts:
      add(clip1, [85%])  # returns clip 1 alone (3 seconds). Confidence: 85%
      add(clip2, [])     # nothing to report, the species is not in the newest clip
    """

    def __init__(self, window_size: int, min_clips_to_merge: int, overlap_time: float) -> None:
        self._window_size = window_size
        self._min_clips_to_merge = min_clips_to_merge
        self._overlap_time = overlap_time
        self._history: deque[_ClipEntry] = deque(maxlen=window_size)

    def add(
        self,
        clip: AudioClip,
        results: list[AnalysisResult],
        raw_candidates: list[RawCandidate] | None = None,
        analysis_time_ms: int = 0,
    ) -> list[RecordedDetection]:
        """
        Record results for the latest clip and return what to store.

        Called once per clip, and reports only the species the newest clip contains.
        While a bird keeps singing, the same species comes back on several calls in a
        row, each time with more of the window behind it, so the recording grows as the
        song goes on.
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

        return [self._recorded_detection(species) for species in detections]

    def _recorded_detection(self, species: Species) -> RecordedDetection:
        """
        The species as the whole window sees it: the highest confidence it reached, the
        raw output of the clip that scored it, and as much audio as it has earned.
        """
        # The species is in the newest clip, so at least one entry holds it and this
        # cannot come back empty.
        entries = [entry for entry in self._history if species in entry.detections]
        best_entry = max(entries, key=lambda entry: entry.detections[species])
        confidence = best_entry.detections[species]

        if len(entries) >= self._min_clips_to_merge:
            clip = AudioClip.merge([entry.clip for entry in self._history], self._overlap_time)
        else:
            clip = best_entry.clip

        return RecordedDetection(
            clip=clip,
            result=AnalysisResult(species=species, confidence=confidence),
            analysis_time_ms=best_entry.analysis_time_ms,
            raw_candidates=best_entry.raw_candidates,
        )
