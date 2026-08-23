import logging
import subprocess

logger = logging.getLogger(__name__)

# The units a station's sudoers policy allows, and so the only ones worth asking for.
# install.sh writes that policy from the same four names, and
# tests/unit/test_sudoers_policy.py fails if the two lists ever drift apart.
ALLOWED_UNITS = (
    "backyardchirps-web",
    "backyardchirps-recorder",
    "backyardchirps-update-species",
    "backyardchirps-clip-disk-quota",
)

# Long enough for the recorder to release the microphone and come back, short enough
# that a wedged unit does not hold an HTTP request open.
_TIMEOUT_SECONDS = 30


def restart_unit(unit: str) -> bool:
    """
    Restart a systemd unit, returning whether it worked.

    Goes through sudo, which install.sh grants for the station's own units and nothing
    else. A development machine has no such units and no such grant, so this returns
    False there rather than failing the request that called it.

    Only a unit in ALLOWED_UNITS is passed to sudo. Callers name a unit as a constant
    rather than taking one from a request, and this check is what keeps that true even
    if one day a caller forgets.
    """
    if unit not in ALLOWED_UNITS:
        logger.error("Refusing to restart %s, which is not a unit this station manages", unit)
        return False

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
