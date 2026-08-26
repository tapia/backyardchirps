import logging
import subprocess

logger = logging.getLogger(__name__)

# Which units a station's sudoers policy allows, and which verbs on each. The policy the
# package ships is the same list written out, and tests/unit/test_sudoers_policy.py fails
# if the two drift apart.
MANAGED_UNITS = {
    "backyardchirps-web": ("start", "stop", "restart"),
    "backyardchirps-recorder": ("start", "stop", "restart"),
    "backyardchirps-update-species": ("start", "stop", "restart"),
    "backyardchirps-clip-disk-quota": ("start", "stop", "restart"),
    "backyardchirps-update": ("start",),
    "backyardchirps-rollback": ("start",),
    "backyardchirps-check-update": ("start",),
}

# Units this station starts without waiting for them to finish.
#
# Both are oneshots that run for minutes, and `systemctl start` on a oneshot does not return
# until the unit is done. Waiting is impossible here for a second reason as well: the update
# stops the web process half way through, so the request doing the waiting is killed by the
# very thing it started, and the browser is told the update failed while it is in fact
# working. Neither is worth waiting for anyway, because the status file is what reports
# progress and both scripts write it from the moment they start.
STARTED_WITHOUT_WAITING = ("backyardchirps-update", "backyardchirps-rollback")

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


def systemctl_arguments(unit: str, verb: str) -> list[str]:
    """
    The exact command this station runs for one unit and verb.

    sudo matches a command by its whole argument list rather than by its name, so the policy
    has to spell out every argument, `--no-block` included. Both the call below and the
    shipped policy are read from here, which is what stops the two drifting apart.
    """
    if verb == "start" and unit in STARTED_WITHOUT_WAITING:
        return ["systemctl", "start", "--no-block", unit]
    return ["systemctl", verb, unit]


def _run_systemctl(verb: str, unit: str) -> bool:
    if verb not in MANAGED_UNITS.get(unit, ()):
        logger.error("Refusing to %s %s: not a pair this station's policy allows", verb, unit)
        return False

    try:
        result = subprocess.run(
            ["sudo", *systemctl_arguments(unit, verb)],
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
