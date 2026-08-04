from __future__ import annotations

import tempfile
import wave
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

import numpy as np
from django.conf import settings

from backyardchirps.features.recording.audio.detection import AnalysisResult


class AudioClip:
    def __init__(self, recorded_at: datetime, audio: np.ndarray, sample_rate: int):
        self.recorded_at = recorded_at
        self._audio = audio
        self._sample_rate = sample_rate

    @classmethod
    def from_wav(cls, path: Path, recorded_at: datetime) -> "AudioClip":
        """
        Load a saved mono 16-bit WAV back into an AudioClip, to analyze it again.
        """
        with wave.open(str(path), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            frames = wav_file.readframes(wav_file.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767.0
        return cls(recorded_at=recorded_at, audio=audio, sample_rate=sample_rate)

    @property
    def samples(self) -> np.ndarray:
        return self._audio

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @contextmanager
    def as_wav(self) -> Iterator[Path]:
        """
        Writes audio to a temporary WAV file, deleted when the context manager exits.
        """
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            self._write_wav(Path(tmp.name))
            yield Path(tmp.name)

    def save_if_needed(self, analysis_result: AnalysisResult) -> Path:
        return self._save_to_clips_dir(analysis_result)

    def duration_seconds(self) -> float:
        """
        The clip length in seconds, rounded to a tenth, which is as much precision as
        the recordings list shows.
        """
        return round(len(self._audio) / self._sample_rate, 1)

    @classmethod
    def merge(cls, clips: list["AudioClip"], overlap_time: float) -> "AudioClip":
        """
        Join consecutive overlapping clips into one longer clip.

        Because the recorder overlaps its clips, each one starts with audio already
        heard at the end of the clip before it. Every clip after the first therefore
        drops its first overlap_time seconds, and only the new audio is added.
        """
        merged_audio = clips[0]._audio.copy()
        for clip in clips[1:]:
            overlap_samples = int(overlap_time * clip._sample_rate)
            merged_audio = np.concatenate([merged_audio, clip._audio[overlap_samples:]])
        return cls(
            recorded_at=clips[-1].recorded_at,
            audio=merged_audio,
            sample_rate=clips[0]._sample_rate,
        )

    @staticmethod
    def delete_clip(path_str: str | None) -> None:
        if path_str:
            try:  # noqa: SIM105
                Path(path_str).unlink(missing_ok=True)
            except Exception:
                pass

    def _save_to_clips_dir(self, analysis_result: AnalysisResult) -> Path:
        path = self._clip_path_for(analysis_result)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_wav(path)
        return path

    def _clip_path_for(self, analysis_result: AnalysisResult) -> Path:
        recorded_at_str = self.recorded_at.strftime("%Y%m%d_%H%M%S")
        safe_name = analysis_result.species.scientific_name.replace(" ", "_")
        confidence = int(analysis_result.confidence * 100)
        return Path(settings.CLIPS["save_dir"]) / f"{recorded_at_str}_{safe_name}_{confidence}pct.wav"

    def _write_wav(self, path: Path) -> None:
        audio_int16 = (self._audio * 32767).astype(np.int16)
        with wave.open(str(path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._sample_rate)
            wf.writeframes(audio_int16.tobytes())
