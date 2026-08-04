from datetime import datetime
from datetime import timezone
from pathlib import Path

from django.test import override_settings

from backyardchirps.shared.recorder_heartbeat import RecorderHeartbeat
from backyardchirps.shared.recorder_heartbeat import read_heartbeat
from backyardchirps.shared.recorder_heartbeat import write_heartbeat


def _heartbeat() -> RecorderHeartbeat:
    return RecorderHeartbeat(
        recorded_at=datetime(2024, 6, 15, 8, 0, 0, tzinfo=timezone.utc),
        queue_depth=3,
        queue_depth_peak=12,
        analysis_ms_avg=1420,
        budget_ms=1500,
    )


def test_write_then_read_round_trips_the_heartbeat(tmp_path: Path) -> None:
    path = tmp_path / "recorder_heartbeat.json"
    with override_settings(RECORDER_HEARTBEAT_FILE=path):
        write_heartbeat(_heartbeat())

        assert read_heartbeat() == _heartbeat()


def test_write_creates_the_parent_directory(tmp_path: Path) -> None:
    path = tmp_path / "generated" / "recorder_heartbeat.json"
    with override_settings(RECORDER_HEARTBEAT_FILE=path):
        write_heartbeat(_heartbeat())

        assert path.exists()


def test_read_returns_none_when_the_file_is_missing(tmp_path: Path) -> None:
    with override_settings(RECORDER_HEARTBEAT_FILE=tmp_path / "missing.json"):
        assert read_heartbeat() is None


def test_read_returns_none_for_a_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "recorder_heartbeat.json"
    path.write_text("{ not valid json")
    with override_settings(RECORDER_HEARTBEAT_FILE=path):
        assert read_heartbeat() is None
