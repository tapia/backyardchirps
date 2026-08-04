from datetime import datetime
from datetime import timezone
from typing import Any

import psutil
from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.settings.app_settings import SERVER_STATUS_THRESHOLDS
from backyardchirps.shared.recorder_heartbeat import read_heartbeat


@api_view(["GET"])
@permission_classes([IsAdminUser])
def server_status(request: Request) -> Response:
    """
    A snapshot of the server's resources. The alert flag is true as soon as any one
    metric reaches its threshold.
    """
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    cpu_temperature = _cpu_temperature()
    cpu_load = round(psutil.cpu_percent(interval=0.2), 1)
    memory_percent = round(memory.used / memory.total * 100, 1)
    disk_percent = round(disk.percent, 1)
    disk_percent_threshold = Settings.get(SettingsKey.CLIPS_MAX_DISK_USAGE_PERCENT)

    cpu_temperature_alert = (
        cpu_temperature is not None and cpu_temperature >= SERVER_STATUS_THRESHOLDS["cpu_temperature"]
    )
    cpu_load_alert = cpu_load >= SERVER_STATUS_THRESHOLDS["cpu_load"]
    memory_alert = memory_percent >= SERVER_STATUS_THRESHOLDS["memory_percent"]
    disk_alert = disk_percent >= disk_percent_threshold
    queue = _sound_processing_queue()

    return Response(
        {
            "version": settings.VERSION,
            "cpu_temperature": cpu_temperature,
            "cpu_temperature_alert": cpu_temperature_alert,
            "cpu_load": cpu_load,
            "cpu_load_alert": cpu_load_alert,
            "memory_used_mb": round(memory.used / 1024 / 1024),
            "memory_total_mb": round(memory.total / 1024 / 1024),
            "memory_percent": memory_percent,
            "memory_alert": memory_alert,
            "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 1),
            "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 1),
            "disk_percent": disk_percent,
            "disk_alert": disk_alert,
            "sound_processing_queue": queue,
            "alert": cpu_temperature_alert or cpu_load_alert or memory_alert or disk_alert or queue["alert"],
            "thresholds": {
                "cpu_temperature": SERVER_STATUS_THRESHOLDS["cpu_temperature"],
                "cpu_load": SERVER_STATUS_THRESHOLDS["cpu_load"],
                "memory_percent": SERVER_STATUS_THRESHOLDS["memory_percent"],
                "disk_percent": disk_percent_threshold,
                "sound_processing_queue_load": SERVER_STATUS_THRESHOLDS["sound_processing_queue_load"],
            },
        }
    )


def _sound_processing_queue() -> dict[str, Any]:
    """
    The recorder's clip backlog, taken from its latest heartbeat.

    A missing or old heartbeat means the recorder is not running, and gives
    available=False. The queue card then says so, instead of showing a frozen snapshot as
    though it were live.

    load_percent compares the average analysis time against the time available per clip.
    At 100% the queue stops going down, which is why this is the number worth watching.
    """
    heartbeat = read_heartbeat()
    if heartbeat is None:
        return {"available": False, "alert": False}
    age_seconds = (datetime.now(timezone.utc) - heartbeat.recorded_at).total_seconds()
    if age_seconds > settings.RECORDER_HEARTBEAT_STALE_SECONDS:
        return {"available": False, "alert": False}

    load_percent = round(heartbeat.analysis_ms_avg / heartbeat.budget_ms * 100, 1) if heartbeat.budget_ms else 0.0
    return {
        "available": True,
        "depth": heartbeat.queue_depth,
        "depth_peak": heartbeat.queue_depth_peak,
        "analysis_ms": heartbeat.analysis_ms_avg,
        "budget_ms": heartbeat.budget_ms,
        "load_percent": load_percent,
        "alert": load_percent >= SERVER_STATUS_THRESHOLDS["sound_processing_queue_load"],
    }


def _cpu_temperature() -> float | None:
    """
    Return CPU temperature in Celsius, or None if unavailable on this platform.
    """
    if not hasattr(psutil, "sensors_temperatures"):
        return None
    temperatures = psutil.sensors_temperatures()
    if not temperatures:
        return None
    for sensor_name in ("cpu_thermal", "coretemp", "k10temp", "acpitz"):
        entries = temperatures.get(sensor_name)
        if entries:
            return float(round(entries[0].current, 1))
    first_entries = next(iter(temperatures.values()), None)
    if first_entries:
        return float(round(first_entries[0].current, 1))
    return None
