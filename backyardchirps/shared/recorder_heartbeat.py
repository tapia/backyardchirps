import json
import os
from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings


@dataclass(frozen=True)
class RecorderHeartbeat:
    """
    A snapshot of the recorder's clip queue, written for the server to read back.
    """

    recorded_at: datetime
    queue_depth: int
    queue_depth_peak: int
    analysis_ms_avg: int
    budget_ms: int


def write_heartbeat(heartbeat: RecorderHeartbeat) -> None:
    path: Path = settings.RECORDER_HEARTBEAT_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(heartbeat)
    payload["recorded_at"] = heartbeat.recorded_at.isoformat()
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(payload))
    os.replace(temporary_path, path)


def read_heartbeat() -> RecorderHeartbeat | None:
    path: Path = settings.RECORDER_HEARTBEAT_FILE
    try:
        payload = json.loads(path.read_text())
        return RecorderHeartbeat(
            recorded_at=datetime.fromisoformat(payload["recorded_at"]),
            queue_depth=payload["queue_depth"],
            queue_depth_peak=payload["queue_depth_peak"],
            analysis_ms_avg=payload["analysis_ms_avg"],
            budget_ms=payload["budget_ms"],
        )
    except (OSError, ValueError, KeyError):
        return None
