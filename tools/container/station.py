"""
A throwaway station in a container, and everything needed to bring one up.

Everything here drives the machine. The assertions live in test_container_apt.py and the
wiring between the two in conftest.py.
"""

import dataclasses
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

CONTAINER_DIR = Path(__file__).resolve().parent
REPO_ROOT = CONTAINER_DIR.parent.parent

IMAGE = "backyardchirps-test"
CONTAINER_NAME = "backyardchirps-test-station"

# The virtualenv the deps package owns. Every station has this one interpreter and no other:
# nothing is built on the machine, so there is nothing else it could be.
VENV_PYTHON = "/opt/backyardchirps/venv/bin/python"
DATA_DIR = "/var/lib/backyardchirps"
SERVICE_USER = "backyardchirps"
INSTALL_LOG = "/var/log/backyardchirps-install.log"

DAEMONS = ("backyardchirps-web", "backyardchirps-recorder")
TIMED_JOBS = ("backyardchirps-update-species", "backyardchirps-clip-disk-quota", "backyardchirps-check-update")

# A recording, standing in for everything a station has collected. The data directory is what an
# update must not touch, and a file under clips/ is the part a user would never forgive losing.
KEPT_CLIP = f"{DATA_DIR}/clips/kept-across-the-update.wav"

# The station is given an owner the short way rather than through the wizard's HTTP flow, because
# finishing that flow needs a microphone and a recorder that can start, which is exactly what
# this container does not have. What is under test is the installer's decision, and that keys on
# the admin account and the token file alone.
CREATE_ADMIN = (
    'from backyardchirps.features.setup import queries; queries.create_superuser("tester", "TestStation2026x")'
)

# Booting systemd under docker needs a private cgroup namespace and nothing else. Do not add
# -v /sys/fs/cgroup:/sys/fs/cgroup here: that is the cgroup v1 recipe, and every current host is
# cgroup v2 only. On v2 docker mounts a cgroup2 filesystem rooted at the container's own cgroup,
# and bind-mounting the host tree over it leaves systemd looking at a root that is not its own,
# where it never finishes booting. That is silent apart from the boot timeout below.
RUN_FLAGS = ["--privileged", "--cgroupns=private", "--tmpfs", "/run", "--tmpfs", "/run/lock", "--tmpfs", "/tmp"]

# systemd is given this long to finish booting. `degraded` counts: this image deliberately
# removes units that want hardware it does not have.
BOOT_TIMEOUT_SECONDS = 30


@dataclasses.dataclass(frozen=True)
class Station:
    """
    A container running systemd, driven from outside through `docker exec`.
    """

    name: str
    python: str = VENV_PYTHON

    def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["docker", "exec", self.name, *command],
            capture_output=True,
            text=True,
            check=False,
        )

    def run_as_service_user(self, shell_command: str) -> subprocess.CompletedProcess[str]:
        """
        The service user has no login shell, so it is reached through sudo rather than by
        execing as it, which is also how apply.sh reaches it.
        """
        return self.run(["sudo", "-u", SERVICE_USER, "bash", "-c", shell_command])

    def sql(self, statement: str) -> str:
        """
        Run one statement against the station's database as the service user.

        Through the release's own interpreter rather than the sqlite3 command line tool,
        which is installed in this image for the test's convenience and not on a real
        station.
        """
        script = (
            "import sqlite3, sys; "
            f"connection = sqlite3.connect('{DATA_DIR}/detections.db'); "
            "rows = connection.execute(sys.argv[1]).fetchall(); "
            "connection.commit(); "
            "print('\\n'.join(str(row[0]) for row in rows))"
        )
        return self.run_as_service_user(f'{self.python} -c "{script}" "{statement}"').stdout.strip()

    def sudo_permits(self, command: str) -> bool:
        """
        Whether the service user's sudo policy allows a command, asked without running it.

        `sudo -l COMMAND` exits 0 when the policy permits it and 1 when it does not, and
        prints the answer either way rather than executing anything. The listing needs no
        password, since every entry the service user has is NOPASSWD, and `-n` makes a
        prompt an error instead of a hang if that ever stops being true.
        """
        return self.run_as_service_user(f"sudo -n -l {command}").returncode == 0

    def succeeds(self, command: list[str]) -> bool:
        return self.run(command).returncode == 0

    def output_of(self, command: list[str]) -> str:
        return self.run(command).stdout.strip()

    def path_exists(self, path: str) -> bool:
        return self.succeeds(["test", "-e", path])

    def read(self, path: str) -> str:
        return self.output_of(["cat", path])

    def real_path(self, path: str) -> str:
        return self.output_of(["readlink", "-f", path])

    def owner_of(self, path: str) -> str:
        return self.output_of(["stat", "-c", "%U", path])

    def mode_of(self, path: str) -> str:
        return self.output_of(["stat", "-c", "%a", path])

    def inode_of(self, path: str) -> str:
        return self.output_of(["stat", "-c", "%i", path])

    def groups_of(self, account: str) -> list[str]:
        return self.output_of(["id", "-nG", account]).split()

    def unit_property(self, unit: str, name: str) -> str:
        return self.output_of(["systemctl", "show", unit, f"--property={name}", "--value"])

    def unit_is_active(self, unit: str) -> bool:
        return self.succeeds(["systemctl", "is-active", "--quiet", unit])

    def unit_is_enabled(self, unit: str) -> bool:
        return self.succeeds(["systemctl", "is-enabled", "--quiet", unit])

    def failed_units(self) -> list[str]:
        """
        Expected to find something: this image deliberately strips units that want real hardware,
        so the machine boots `degraded`. Named rather than passed over, so a unit that starts
        failing for a new reason is visible instead of hiding inside a state the test tolerates.
        """
        listed = self.output_of(["systemctl", "list-units", "--failed", "--no-legend", "--no-pager"])
        # systemd marks each line with a bullet before the unit name, even with --no-legend and
        # even when nothing is reading it as a terminal. Taking the first field verbatim reports
        # a list of bullets, which is what the shell version this replaced used to print.
        names = [re.sub(r"^\W+", "", line.strip()).split() for line in listed.splitlines()]
        return [fields[0] for fields in names if fields]

    def files_matching(self, directory: str, pattern: str) -> list[str]:
        return self.output_of(["find", directory, "-name", pattern]).splitlines()

    def http_status(self, url: str) -> str:
        return self.output_of(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url])

    def http_json(self, url: str) -> dict[str, Any]:
        body = self.output_of(["curl", "-s", url])
        return dict(json.loads(body))

    def copy_in(self, source: Path, destination: str) -> None:
        """
        Written through `tee` on the far end of `docker exec -i`, which needs nothing from docker
        beyond a pipe and lands the file owned by root, as a download would.
        """
        with source.open("rb") as handle:
            result = subprocess.run(
                ["docker", "exec", "-i", self.name, "tee", destination],
                stdin=handle,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        if result.returncode != 0:
            raise RuntimeError(f"Could not copy {source} into the station: {result.stderr}")

    def install_log_tail(self, lines: int = 60) -> str:
        """
        Every failure message points at the install log, and on CI nobody can open a shell to
        read it, so it comes out in the failure instead. The log may not exist yet, which is why
        this is allowed to find nothing.
        """
        if not self.succeeds(["test", "-f", INSTALL_LOG]):
            return ""
        return self.output_of(["tail", "-n", str(lines), INSTALL_LOG])

    def container_logs(self, lines: int = 40) -> str:
        result = subprocess.run(
            ["docker", "logs", self.name],
            capture_output=True,
            text=True,
            check=False,
        )
        return "\n".join((result.stdout + result.stderr).splitlines()[-lines:])


def require_docker() -> None:
    """
    Checked once up front, because everything after this point fails as a missing command deep
    inside a fixture otherwise.
    """
    if shutil.which("docker") is None:
        raise RuntimeError("docker is not installed. See the header of test_container_apt.py.")


MODEL_CACHE_DIR = Path(
    os.environ.get("BACKYARDCHIRPS_MODEL_CACHE", Path.home() / ".cache" / "backyardchirps-container-models")
)
STATION_MODELS_DIR = f"{DATA_DIR}/models"


def seed_models(station: Station) -> bool:
    """
    Put cached models where a fresh install will find them, before install.sh runs.

    apply.sh skips a download when the file is already there at the published size, so this
    is not a stub: the same check a real station makes on its second deploy is what decides.
    They land root-owned and world-readable, which is enough, since provision-data-dir.sh
    creates the data directory without touching what is already inside it.
    """
    cached = sorted(MODEL_CACHE_DIR.glob("*")) if MODEL_CACHE_DIR.is_dir() else []
    if not cached:
        return False

    station.run(["mkdir", "-p", STATION_MODELS_DIR])
    for path in cached:
        station.copy_in(path, f"{STATION_MODELS_DIR}/{path.name}")
    station.run(["chmod", "-R", "a+rX", STATION_MODELS_DIR])
    return True


def save_models(station: Station) -> None:
    """
    Keep what this run downloaded, so the next one does not have to.
    """
    MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    listed = station.output_of(["ls", "-1", STATION_MODELS_DIR])
    for name in [line.strip() for line in listed.splitlines() if line.strip()]:
        subprocess.run(
            ["docker", "cp", f"{station.name}:{STATION_MODELS_DIR}/{name}", str(MODEL_CACHE_DIR / name)],
            capture_output=True,
            check=False,
        )


def build_image() -> None:
    result = subprocess.run(
        ["docker", "build", "-t", IMAGE, str(CONTAINER_DIR)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Building the {IMAGE} image failed:\n{result.stdout}\n{result.stderr}")


def boot(name: str = CONTAINER_NAME, python: str | None = None) -> Station:
    """
    A machine that has never worked before. Anything that only passes because of state left
    behind by an earlier attempt fails here, which is exactly the class of problem an installer
    has.

    The two chains bring up one machine each, under different names, so neither can pass
    because of something the other left behind.
    """
    remove(Station(name=name))
    result = subprocess.run(
        ["docker", "run", "-d", "--name", name, *RUN_FLAGS, IMAGE],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not start the container:\n{result.stderr}")

    station = Station(name=name, python=python) if python else Station(name=name)
    _wait_for_systemd(station)
    return station


def remove(station: Station) -> None:
    subprocess.run(
        ["docker", "rm", "-f", station.name],
        capture_output=True,
        check=False,
    )


def _wait_for_systemd(station: Station) -> None:
    """
    `systemctl is-system-running` exits non-zero for every state except `running`, and `degraded`
    is a state this container is expected to reach: it deliberately removes units that want
    hardware it does not have. So the state is read as a value and judged on that.
    """
    deadline = time.monotonic() + BOOT_TIMEOUT_SECONDS
    state = ""
    while time.monotonic() < deadline:
        state = station.output_of(["systemctl", "is-system-running"])
        if state in ("running", "degraded"):
            return
        time.sleep(1)

    # Nothing the station does has run yet, so the install log does not exist. What init itself
    # said is the only place the reason appears, and without it the failure reads as "systemd
    # never came up" and nothing more.
    raise RuntimeError(
        f"systemd never came up (state: {state or 'none'}). Re-run with --keep-station and look "
        f"at 'systemctl status'.\n"
        f"--- container output ---\n{station.container_logs()}\n"
        f"--- failed units ---\n{', '.join(station.failed_units()) or 'none'}"
    )
