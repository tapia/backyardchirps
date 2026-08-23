"""
A throwaway station in a container, and everything needed to put a release on it.

Everything here drives the machine. The assertions live in test_container_install.py, and the
wiring between the two in conftest.py.

Nothing in here is specific to one test. `install` is called three times over a run: once on a
clean machine, once again on the same version to prove a re-install keeps a configured station,
and once with a newer version to prove an update.
"""

import dataclasses
import json
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

INSTALL_ROOT = "/opt/backyardchirps"
APP_DIR = f"{INSTALL_ROOT}/current"
DATA_DIR = "/var/lib/backyardchirps"
SERVICE_USER = "backyardchirps"
INSTALL_LOG = "/var/log/backyardchirps-install.log"

# Where the installer, the uninstaller and the tarballs are put inside the station. They are
# copied in rather than mounted, so nothing on the host is reachable from the machine under
# test.
INSTALL_DIR = "/tmp/install"

DAEMONS = ("backyardchirps-web", "backyardchirps-recorder")
TIMED_JOBS = ("backyardchirps-update-species", "backyardchirps-clip-disk-quota")

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
class Release:
    """
    A tarball staged on the host, built from this checkout and never published.
    """

    version: str
    tarball_name: str
    tarball_path: Path


@dataclasses.dataclass(frozen=True)
class Snapshot:
    """
    What a station looked like before it was updated, for the tests that compare across it.
    """

    release: str
    secret_key: str
    database_inode: str


@dataclasses.dataclass(frozen=True)
class Reinstalled:
    """
    A station that already had an owner when the installer ran again, and what that run printed.
    The output matters as much as the state: an installer that offers a token for a station with
    an owner is telling its owner to undo their own setup.
    """

    station: "Station"
    output: str


@dataclasses.dataclass(frozen=True)
class Updated:
    """
    A station moved to a newer release, with what it looked like before.
    """

    station: "Station"
    version: str
    before: Snapshot


@dataclasses.dataclass(frozen=True)
class Station:
    """
    A container running systemd, driven from outside through `docker exec`.
    """

    name: str

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
        raise RuntimeError("docker is not installed. See the header of test_container_install.py.")


def build_release(output_dir: Path, version_suffix: str = "") -> Release:
    """
    The station installs a release, not a checkout, so that is what it gets. Nothing is tagged or
    published: tools/build_tarball.py writes the same artifact CI would, into a temporary
    directory that is thrown away at the end.

    This is also what lets the image stay free of Node. The tarball carries a prebuilt frontend,
    so apply.sh has nothing to build.
    """
    command = [
        "uv",
        "run",
        "--no-project",
        "python",
        str(REPO_ROOT / "tools" / "build_tarball.py"),
        "--output-dir",
        str(output_dir),
    ]
    if version_suffix:
        command += ["--version-suffix", version_suffix]

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Building the release tarball failed:\n{result.stderr}")

    # key=value lines on stdout, progress on stderr. Parsed rather than eval'd, which is what the
    # shell version had to do: a failing build inside `eval "$(...)"` sets no variables and stops
    # nothing, so the error surfaced several steps later under a different name.
    built = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return Release(
        version=built["VERSION"],
        tarball_name=built["TARBALL_NAME"],
        tarball_path=Path(built["TARBALL_PATH"]),
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


def boot() -> Station:
    """
    A machine that has never worked before. Anything that only passes because of state left
    behind by an earlier attempt fails here, which is exactly the class of problem an installer
    has.
    """
    remove(Station(name=CONTAINER_NAME))
    result = subprocess.run(
        ["docker", "run", "-d", "--name", CONTAINER_NAME, *RUN_FLAGS, IMAGE],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Could not start the container:\n{result.stderr}")

    station = Station(name=CONTAINER_NAME)
    _wait_for_systemd(station)
    return station


def remove(station: Station) -> None:
    subprocess.run(
        ["docker", "rm", "-f", station.name],
        capture_output=True,
        check=False,
    )


def copy_release_in(station: Station, release: Release) -> None:
    """
    install.sh is not in the tarball: it is the file a user downloads on its own, before there is
    a release on the machine. So it comes from the checkout, which is what the one-line curl
    would fetch from the default branch.
    """
    station.run(["mkdir", "-p", INSTALL_DIR])
    station.copy_in(REPO_ROOT / "install.sh", f"{INSTALL_DIR}/install.sh")
    station.copy_in(REPO_ROOT / "uninstall.sh", f"{INSTALL_DIR}/uninstall.sh")
    station.copy_in(release.tarball_path, f"{INSTALL_DIR}/{release.tarball_name}")


def install(station: Station, release: Release) -> subprocess.CompletedProcess[str]:
    """
    --ignore-preflight because a container is not a Pi: there is no /proc/device-tree/model and
    no sound card. Everything after the hardware checks is the same code a real install runs, and
    the checks themselves are covered by tests/unit/test_preflight.py.
    """
    return station.run(
        [
            "bash",
            f"{INSTALL_DIR}/install.sh",
            "--tarball",
            f"{INSTALL_DIR}/{release.tarball_name}",
            "--data-dir",
            DATA_DIR,
            "--ignore-preflight",
        ]
    )


def snapshot(station: Station) -> Snapshot:
    return Snapshot(
        release=station.real_path(APP_DIR),
        secret_key=station.output_of(["grep", "^SECRET_KEY=", f"{DATA_DIR}/.env"]),
        database_inode=station.inode_of(f"{DATA_DIR}/detections.db"),
    )


def uninstall(station: Station) -> subprocess.CompletedProcess[str]:
    """
    Without --all, so it has to remove the software and keep every recording. A station being
    taken apart must not take the data with it by accident.
    """
    return station.run(["bash", f"{INSTALL_DIR}/uninstall.sh", "--data-dir", DATA_DIR])


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
