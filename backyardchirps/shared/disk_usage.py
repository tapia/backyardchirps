from pathlib import Path

import psutil


def get_usage_percent(path: Path) -> float:
    """
    How full the filesystem holding path is. Not the size of path itself.
    """
    return psutil.disk_usage(str(path)).percent
