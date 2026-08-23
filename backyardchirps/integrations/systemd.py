import logging
import subprocess

logger = logging.getLogger(__name__)

# Which units a station's sudoers policy allows, and which verbs on each. install.sh
# writes that policy from the same pairs, and tests/unit/test_sudoers_policy.py fails if
# the two drift apart.
MANAGED_UNITS = {
    "backyardchirps-web": ("start", "stop", "restart"),
    "backyardchirps-recorder": ("start", "stop", "restart"),
    "backyardchirps-update-species": ("start", "stop", "restart"),
    "backyardchirps-clip-disk-quota": ("start", "stop", "restart"),
    "backyardchirps-update": ("start",),
    "backyardchirps-rollback": ("start",),
}

# Long enough for the recorder to release the microphone and come back, short enough
# that a wedged unit does not hold an HTTP request open.
_TIMEOUT_SECONDS = 30


def restart_unit(unit: str) -> bool:
    """
    Restart a systemd unit, returning whether it worked.
    """
    return _run_systemctl("restart", unit)


def start_unit(unit: str) -> bool:
    """
    Start a systemd unit, returning whether it worked.
    """
    return _run_systemctl("start", unit)


def _run_systemctl(verb: str, unit: str) -> bool:
    if verb not in MANAGED_UNITS.get(unit, ()):
        logger.error("Refusing to %s %s: not a pair this station's policy allows", verb, unit)
        return False

    try:
        result = subprocess.run(
            ["sudo", "systemctl", verb, unit],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        logger.exception("Could not %s %s", verb, unit)
        return False

    if result.returncode != 0:
        logger.warning("Running %s on %s failed: %s", verb, unit, result.stderr.strip())
        return False
    return True
