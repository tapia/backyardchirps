"""
Everything needed to install a station from packages, on a machine in a container.

The assertions live in test_container_apt.py and the wiring in conftest.py, the same split
the tarball chain uses. What is different is what is under test: dpkg unpacks the files and
the maintainer scripts do the rest, so this exercises preinst, postinst, prerm and postrm,
which is where every decision install.sh used to make now lives.

The repository is a directory inside the machine, read through a `file:` source. That needs
no HTTP server and no signing key, and it is still apt's real download-and-unpack path: the
only thing being skipped is the transport, which is the part this project does not write.
"""

import dataclasses
import json
import subprocess
from pathlib import Path
from typing import Any

from station import DATA_DIR
from station import SERVICE_USER
from station import VENV_PYTHON
from station import Station

CONTAINER_DIR = Path(__file__).resolve().parent
REPO_ROOT = CONTAINER_DIR.parent.parent

# A second machine, beside the one the tarball chain owns, so neither run can pass because
# of state the other left behind.
APT_CONTAINER_NAME = "backyardchirps-test-apt-station"

# A third machine, for the one thing that happens once per station and can never be
# retried: installing the packages over a station the tarball installer set up.
TAKEOVER_CONTAINER_NAME = "backyardchirps-test-takeover-station"

# Where a packaged station keeps its parts. These are the paths the packages install to,
# repeated here rather than imported: a test that reads them from the code under test would
# agree with it whatever either one said.
CODE_DIR = "/usr/lib/backyardchirps"
SHARE_DIR = "/usr/share/backyardchirps"
MANAGE = f"{CODE_DIR}/bin/manage"

PACKAGE_DIR = "/srv/apt"
SOURCE_FILE = "/etc/apt/sources.list.d/backyardchirps.sources"

# Trusted: yes because nothing here is signed. Signing and a real repository come with the
# published one; what this has to prove is that the packages install, upgrade and remove
# cleanly, which is a dpkg question rather than a transport one.
SOURCE = f"""Types: deb
URIs: file:{PACKAGE_DIR}
Suites: ./
Trusted: yes
"""

# What the updater will pass, and the reason it will: a broken Debian mirror must not make
# a station report "update check failed", and our daily poll must not touch the sources an
# owner added for something else.
SCOPED_UPDATE = [
    "apt-get",
    "update",
    "-o",
    f"Dir::Etc::sourcelist={SOURCE_FILE}",
    "-o",
    "Dir::Etc::sourceparts=/dev/null",
    "-o",
    "APT::Get::List-Cleanup=0",
]

# An unattended install must not stop at a conffile prompt: apt would wait for an answer
# nobody is there to give, and the update would hang rather than fail.
UNATTENDED = [
    "-y",
    "-o",
    "Dpkg::Options::=--force-confold",
    "-o",
    "Dpkg::Options::=--force-confdef",
]


@dataclasses.dataclass(frozen=True)
class Packages:
    """
    Packages staged on the host, built from this checkout and never published.
    """

    app_version: str
    paths: list[Path]


@dataclasses.dataclass(frozen=True)
class Installed:
    """
    A machine with the packages on it, and what the install said while it ran.
    """

    station: Station
    version: str
    output: str


@dataclasses.dataclass(frozen=True)
class SelfUpdated:
    """
    A machine that installed a newer version itself, through the privileged updater.
    """

    station: Station
    version: str
    from_version: str
    output: str


@dataclasses.dataclass(frozen=True)
class RolledBack:
    """
    A machine put back on the version it was running before it updated itself.
    """

    station: Station
    from_version: str
    to_version: str
    output: str


@dataclasses.dataclass(frozen=True)
class Upgraded:
    """
    A machine moved to a newer version of the app package, and what it looked like before.
    """

    station: Station
    version: str
    output: str
    database_inode: str
    secret_key: str


def build_packages(output_dir: Path, version_suffix: str = "", only: list[str] | None = None) -> Packages:
    """
    Build the .deb files, exactly as CI would. Nothing is published: they go to a temporary
    directory and are copied into the machine from there.

    The virtualenv comes out of a container and takes minutes on a cold cache, which is why
    the upgrade build asks for the app package alone. That is also the shape of a normal
    release: the code changes and the other two do not.
    """
    command = [
        "uv",
        "run",
        "--no-project",
        "python",
        str(REPO_ROOT / "tools" / "build_packages.py"),
        "--output-dir",
        str(output_dir),
    ]
    if version_suffix:
        command += ["--version-suffix", version_suffix]
    for package in only or []:
        command += ["--only", package]

    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Building the packages failed:\n{result.stdout}\n{result.stderr}")

    built = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return Packages(app_version=built["APP_VERSION"], paths=sorted(output_dir.glob("*.deb")))


def packages_in(directory: Path) -> Packages:
    """
    Packages somebody else already built, which is how CI avoids building them twice: the
    job builds once, runs lintian over the result, and hands the same files to this.
    """
    paths = sorted(directory.glob("*.deb"))
    app = [path for path in paths if path.name.startswith("backyardchirps_")]
    if not app:
        raise RuntimeError(f"No backyardchirps_*.deb in {directory}.")
    # backyardchirps_<version>_<arch>.deb, which is the only place the version is written
    # down out here.
    return Packages(app_version=app[0].name.split("_")[1], paths=paths)


def publish(station: Station, packages: Packages) -> None:
    """
    Put the packages in the machine's own repository and index them, which is what an
    `apt-get update` then reads.
    """
    station.run(["mkdir", "-p", PACKAGE_DIR])
    for path in packages.paths:
        station.copy_in(path, f"{PACKAGE_DIR}/{path.name}")
    indexed = station.run(["bash", "-c", f"cd {PACKAGE_DIR} && apt-ftparchive packages . > Packages"])
    if indexed.returncode != 0:
        raise RuntimeError(f"Could not index the local repository:\n{indexed.stderr}")


def add_source(station: Station) -> None:
    """
    Write the deb822 source, the way install.sh will once there is a repository to point at.
    """
    station.run(["mkdir", "-p", "/etc/apt/sources.list.d"])
    written = station.run(["bash", "-c", f"cat > {SOURCE_FILE} <<'EOF'\n{SOURCE}EOF"])
    if written.returncode != 0:
        raise RuntimeError(f"Could not write the apt source:\n{written.stderr}")


def install(station: Station) -> subprocess.CompletedProcess[str]:
    """
    A first install: a full update, because the dependencies come from Debian's own
    mirrors, and then one package name. Everything else follows from Depends:.
    """
    station.run(["apt-get", "update"])
    return station.run(["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", *UNATTENDED, "backyardchirps"])


def upgrade(station: Station) -> subprocess.CompletedProcess[str]:
    """
    An owner upgrading by hand: look at our own source alone, then install whatever it now
    offers. The button takes the longer path through the privileged updater below.
    """
    station.run(SCOPED_UPDATE)
    return station.run(
        ["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "install", *UNATTENDED, "--only-upgrade", "backyardchirps"]
    )


def remove(station: Station) -> subprocess.CompletedProcess[str]:
    return station.run(["env", "DEBIAN_FRONTEND=noninteractive", "apt-get", "remove", "-y", "backyardchirps"])


def purge(station: Station) -> subprocess.CompletedProcess[str]:
    return station.run(
        [
            "env",
            "DEBIAN_FRONTEND=noninteractive",
            "apt-get",
            "purge",
            "-y",
            "backyardchirps",
            "backyardchirps-deps",
            "backyardchirps-species-data",
        ]
    )


def http_status(station: Station, url: str) -> str:
    """
    Ask the site for a page, through the station's own interpreter.

    curl is not on a packaged station: it was in the tarball path to download a release,
    and apt does the downloading now. Python is there by definition, so this needs nothing
    the package does not already depend on.
    """
    script = (
        "import sys, urllib.error, urllib.request\n"
        "try:\n"
        "    print(urllib.request.urlopen(sys.argv[1], timeout=10).status)\n"
        "except urllib.error.HTTPError as answered:\n"
        "    print(answered.code)\n"
    )
    return station.output_of([VENV_PYTHON, "-c", script, url]).splitlines()[-1]


def installed_version(station: Station, package: str = "backyardchirps") -> str:
    """
    What dpkg says is installed, which is the version apt orders upgrades by.
    """
    return station.output_of(["dpkg-query", "--showformat=${Version}", "--show", package])


def control_field(station: Station, field: str, package: str = "backyardchirps") -> str:
    """
    One field out of the package's control data. The updater reads Released and
    Changelog-Url this way, which is what replaces those two keys of manifest.json.
    """
    for line in station.output_of(["apt-cache", "show", package]).splitlines():
        name, _, value = line.partition(":")
        if name.strip().lower() == field.lower():
            return value.strip()
    return ""


def request_update(station: Station, version: str) -> None:
    """
    Ask for a version the way the web process does, by writing the request row.

    The privileged half reads that row and then asks apt whether the version is real, so
    writing it here is the whole of what an admin clicking the button contributes.
    """
    requested = station.run(
        [
            "sudo",
            "-u",
            SERVICE_USER,
            MANAGE,
            "shell",
            "-c",
            f'from backyardchirps.features.updates import queries; queries.request_version("{version}")',
        ]
    )
    if requested.returncode != 0:
        raise RuntimeError(f"Could not record the update request:\n{requested.stderr}")


def run_updater(station: Station) -> subprocess.CompletedProcess[str]:
    """
    Run the updater the way its unit would, but directly, so its output is readable here
    when it fails rather than only in the machine's journal.
    """
    return station.run([f"{CODE_DIR}/bin/update"])


def run_rollback(station: Station) -> subprocess.CompletedProcess[str]:
    return station.run([f"{CODE_DIR}/bin/rollback"])


def run_check(station: Station) -> subprocess.CompletedProcess[str]:
    return station.run([f"{CODE_DIR}/bin/check-update"])


def update_status(station: Station) -> dict[str, str]:
    """
    The status file the two privileged scripts write and the web process reads.
    """
    raw = station.read(f"{DATA_DIR}/update/status.json")
    return dict(json.loads(raw)) if raw else {}


def available_update(station: Station) -> dict[str, Any]:
    """
    What the station stored about the last check, read back through the application rather
    than out of the file, so this covers the import as well as the check.
    """
    printed = station.output_of(
        [
            "sudo",
            "-u",
            SERVICE_USER,
            MANAGE,
            "shell",
            "-c",
            "import json;"
            "from backyardchirps.features.updates import queries;"
            "result = queries.last_check();"
            "print(json.dumps(None if result is None else "
            "{'version': result.version, 'update_available': result.update_available, 'error': result.error}))",
        ]
    ).splitlines()[-1]
    return dict(json.loads(printed) or {})
