from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np

from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.species.entity import Species

_SAMPLE_RATE = 48000
# Production overlap: clip_duration (3.0s) - step_duration (1.5s).
_OVERLAP_TIME = 1.5


def test_from_wav_round_trips_a_saved_clip(tmp_path: Path) -> None:
    recorded_at = datetime(2026, 6, 17, 4, 13)
    samples = np.array([0.0, 0.5, -0.5, 0.25], dtype=np.float32)
    wav_path = tmp_path / "clip.wav"
    AudioClip(recorded_at=recorded_at, audio=samples, sample_rate=32000)._write_wav(wav_path)

    loaded = AudioClip.from_wav(wav_path, recorded_at)

    assert loaded.sample_rate == 32000
    assert loaded.recorded_at == recorded_at
    # 16-bit PCM round-trip: values return within one quantization step.
    np.testing.assert_allclose(loaded.samples, samples, atol=1e-4)


def test_merge_drops_the_shared_overlap_of_each_following_clip(make_audio_clip: Callable[..., AudioClip]) -> None:
    first = make_audio_clip(seconds=3.0, sample_rate=_SAMPLE_RATE)
    second = make_audio_clip(seconds=3.0, sample_rate=_SAMPLE_RATE)

    merged = AudioClip.merge([first, second], _OVERLAP_TIME)

    # 3 s + (3 s - 1.5 s overlap) = 4.5 s.
    assert merged.duration_seconds() == 4.5


def test_merge_single_clip_is_identity_length(make_audio_clip: Callable[..., AudioClip]) -> None:
    clip = make_audio_clip(seconds=3.0, sample_rate=_SAMPLE_RATE)

    merged = AudioClip.merge([clip], _OVERLAP_TIME)

    assert merged.duration_seconds() == 3.0


def test_merge_overlap_scales_with_sample_rate(make_audio_clip: Callable[..., AudioClip]) -> None:
    # overlap_time is in seconds, so it has to be converted using each clip's own sample
    # rate. A fixed number of samples would be wrong.
    first = make_audio_clip(seconds=3.0, sample_rate=16000)
    second = make_audio_clip(seconds=3.0, sample_rate=16000)

    merged = AudioClip.merge([first, second], _OVERLAP_TIME)

    assert merged.duration_seconds() == 4.5


def test_duration_seconds_rounds_to_a_tenth() -> None:
    # 121440 / 48000 = 2.53 -> rounded to 2.5.
    clip = AudioClip(datetime(2024, 6, 15, 8, 0, 0), np.zeros(121440, dtype=np.float32), _SAMPLE_RATE)
    assert clip.duration_seconds() == 2.5


def test_clip_path_for_builds_expected_filename() -> None:
    clip = AudioClip(datetime(2024, 6, 15, 8, 0, 0), np.zeros(10, dtype=np.float32), _SAMPLE_RATE)
    result = AnalysisResult(species=Species("Turdus merula"), confidence=0.8)

    path = clip._clip_path_for(result)

    assert path.name == "20240615_080000_Turdus_merula_80pct.wav"


def test_delete_clip_removes_file_and_is_idempotent(tmp_path: Path) -> None:
    target = tmp_path / "clip.wav"
    target.write_bytes(b"audio")

    AudioClip.delete_clip(str(target))
    assert not target.exists()

    # Deleting a missing path or None must not raise.
    AudioClip.delete_clip(str(target))
    AudioClip.delete_clip(None)
