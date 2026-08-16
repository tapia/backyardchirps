import logging
import queue
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Self

import numpy as np
import sounddevice as sd

from backyardchirps.features.recording.audio.clip import AudioClip

logger = logging.getLogger(__name__)


class AudioRecorder:
    def __init__(
        self,
        sample_rate: int,
        clip_duration: float,
        step_duration: float | None = None,
        device: int | None = None,
    ):
        self._sample_rate = sample_rate
        self._clip_samples = int(sample_rate * clip_duration)
        self._step_samples = int(sample_rate * (step_duration if step_duration is not None else clip_duration))
        self._device = device
        # Connection to the microphone
        self._stream: Any = None

        # Holds the sound coming from the microphone. Once it holds "clip_duration"
        # seconds, that much is cut off and queued for analysis.
        self._buffer = np.array([], dtype=np.float32)

        # Thread-safe queue of clips waiting to be analyzed
        self._queue: queue.Queue[AudioClip] = queue.Queue()

    def __enter__(self) -> Self:
        self._stream = sd.InputStream(
            samplerate=self._sample_rate,
            channels=1,
            device=self._device,
            callback=self._callback,
            dtype=np.float32,
        )
        self._stream.start()
        return self

    def __exit__(self, *_: object) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()

    def next_clip(self, timeout: float = 1.0) -> AudioClip:
        """
        Raises queue.Empty on timeout.
        """
        return self._queue.get(timeout=timeout)

    def pending_clips(self) -> int:
        return self._queue.qsize()

    def _callback(self, indata: np.ndarray, frames: int, time: Any, status: Any) -> None:
        """
        Called by sounddevice on each audio chunk.

        New samples go into the buffer, and every time it holds `clip_duration` seconds
        they come back out as a clip. The buffer then advances by `step_duration` rather
        than by a full clip, so clips overlap and a call landing between two of them is
        still recorded whole.

        Example with clip_duration=3s, step_duration=1.5s:
          clip 1: from t=0.0s to t=3.0s
          clip 2: from t=1.5s  to t=4.5s  (shares 1.5s with clip 1)
          clip 3: from t=3.0s to t=6.0s  (shares 1.5s with clip 2)
        """
        # sounddevice reports input overflow here, which means the machine could not keep
        # up and audio was lost. Without this line that loss leaves no trace at all.
        if status:
            logger.warning("Audio input problem: %s", status)

        self._buffer = np.concatenate([self._buffer, indata[:, 0]])
        while len(self._buffer) >= self._clip_samples:
            audio = self._buffer[: self._clip_samples].copy()
            self._buffer = self._buffer[self._step_samples :]  # advance by step, not clip
            self._queue.put(
                AudioClip(
                    recorded_at=datetime.now(timezone.utc),
                    audio=audio,
                    sample_rate=self._sample_rate,
                )
            )
