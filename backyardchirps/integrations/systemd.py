import logging
import subprocess

logger = logging.getLogger(__name__)

# Long enough for the recorder to release the microphone and come back, short enough
# that a wedged unit does not hold an HTTP request open.
_TIMEOUT_SECONDS = 30


def restart_unit(unit: str) -> bool:
    """
    Restart a systemd unit, returning whether it worked.

    Goes through sudo, which install.sh grants for the station's own units and nothing
    else. A development machine has no such units and no such grant, so this returns
    False there rather than failing the request that called it.

    The unit name comes from the caller and never from a request. Nothing here would
    stop a caller passing one through, so nothing may.
    """
    try:
        result = subprocess.run(
            ["sudo", "systemctl", "restart", unit],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("Could not restart %s", unit)
        return False

    if result.returncode != 0:
        logger.warning("Restarting %s failed: %s", unit, result.stderr.strip())
        return False
    return True
