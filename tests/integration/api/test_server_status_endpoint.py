from datetime import datetime
from datetime import timedelta
from datetime import timezone
from pathlib import Path

import pytest
from rest_framework.test import APIClient

from backyardchirps.shared.recorder_heartbeat import RecorderHeartbeat
from backyardchirps.shared.recorder_heartbeat import write_heartbeat

_URL = "/api/server-status/"


@pytest.fixture
def heartbeat_file(tmp_path: Path, settings: object) -> Path:
    path = tmp_path / "recorder_heartbeat.json"
    settings.RECORDER_HEARTBEAT_FILE = path  # type: ignore[attr-defined]
    return path


def _write_recent_heartbeat(analysis_ms_avg: int, queue_depth: int = 3, queue_depth_peak: int = 12) -> None:
    write_heartbeat(
        RecorderHeartbeat(
            recorded_at=datetime.now(timezone.utc),
            queue_depth=queue_depth,
            queue_depth_peak=queue_depth_peak,
            analysis_ms_avg=analysis_ms_avg,
            budget_ms=1500,
        )
    )


def test_queue_reports_load_from_a_recent_heartbeat(admin_client: APIClient, heartbeat_file: Path) -> None:
    _write_recent_heartbeat(analysis_ms_avg=750)

    queue = admin_client.get(_URL).json()["sound_processing_queue"]

    assert queue["available"] is True
    assert queue["depth"] == 3
    assert queue["depth_peak"] == 12
    assert queue["analysis_ms"] == 750
    assert queue["budget_ms"] == 1500
    assert queue["load_percent"] == 50.0
    assert queue["alert"] is False


def test_queue_alerts_and_raises_the_overall_alert_when_load_is_high(
    admin_client: APIClient, heartbeat_file: Path
) -> None:
    _write_recent_heartbeat(analysis_ms_avg=1400)  # 93.3% of the 1500 ms budget

    body = admin_client.get(_URL).json()

    assert body["sound_processing_queue"]["alert"] is True
    assert body["alert"] is True


def test_queue_is_unavailable_without_a_heartbeat(admin_client: APIClient, heartbeat_file: Path) -> None:
    queue = admin_client.get(_URL).json()["sound_processing_queue"]

    assert queue == {"available": False, "alert": False}


def test_queue_is_unavailable_when_the_heartbeat_is_stale(admin_client: APIClient, heartbeat_file: Path) -> None:
    write_heartbeat(
        RecorderHeartbeat(
            recorded_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            queue_depth=3,
            queue_depth_peak=12,
            analysis_ms_avg=750,
            budget_ms=1500,
        )
    )

    queue = admin_client.get(_URL).json()["sound_processing_queue"]

    assert queue["available"] is False


def test_thresholds_include_the_queue_load(admin_client: APIClient, heartbeat_file: Path) -> None:
    thresholds = admin_client.get(_URL).json()["thresholds"]

    assert thresholds["sound_processing_queue_load"] == 80.0
