"""
Build the Debian packages a station installs.

  uv run --no-project python tools/build_packages.py [--output-dir DIR] [--version-suffix +main.a1b2c3d]

This is the one place that decides what a station gets, the way build_tarball.py was for a
release tarball. It stages a tree per package and then runs nfpm over the YAML files in
packaging/nfpm/, which name what goes in. Nothing is published here: it writes .deb files
and prints where they went.

  backyardchirps               the code, the site, the units, the nginx site, the sudoers
                               policy. Rebuilt every release.
  backyardchirps-deps          the virtualenv. Rebuilt when uv.lock changes.
  backyardchirps-species-data  the taxonomy and the species photos.

Those three are what a plain run builds. There is a fourth, built only when asked for by
name because it needs the archive key that only the publish job has:

  backyardchirps-archive-keyring   the key a station trusts and the source it reads.
                                   Needs --apt-key and --apt-base-url.

The virtualenv is built by packaging/Dockerfile in a debian:trixie container, at the path
it will be installed to, so nothing on a Pi ever compiles anything and no shebang has to be
rewritten afterwards. **The container has to be arm64.** On an amd64 machine the wheels
resolve for the wrong platform, and the smoke test at the end of the Dockerfile is what
catches that.

collectstatic runs inside that same container, so the assets are collected by exactly the
Django the station will run rather than by whatever the build machine has.

Output is key=value lines on stdout and progress on stderr, the same shape build_tarball.py
uses, so a caller can do:

  uv run --no-project python tools/build_packages.py --output-dir . >> "$GITHUB_ENV"

--no-project because nothing here needs the project environment. The venv is the
container's job and the wheel is uv's.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from datetime import datetime
from datetime import timezone
from pathlib import Path
from string import Template
from typing import Any
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT))

# Imports nothing but the standard library, which is what lets this run under --no-project.
from backyardchirps.integrations.birdnet import TaxonomyDownloadError
from backyardchirps.integrations.birdnet import check_taxonomy
from backyardchirps.integrations.birdnet import download_taxonomy

PACKAGING = REPO_ROOT / "packaging"
NFPM_DIR = PACKAGING / "nfpm"

# Where a station keeps each part of itself. Every one of these appears in a nfpm YAML as
# well; they are here because the staging tree has to mirror them exactly, which is what
# makes a package's contents readable as "the tree, moved to /".
VENV_PATH = "opt/backyardchirps/venv"
CODE_PATH = "usr/lib/backyardchirps"
SHARE_PATH = "usr/share/backyardchirps"
UNITS_PATH = "usr/lib/systemd/system"

# The venv is bound to one Python minor version: the .pth has to land in its site-packages
# and the bytecode is compiled for it. This is the version Debian trixie ships, and the
# deps package says so with Depends: python3.13.
PYTHON_VERSION = "3.13"

VENV_IMAGE = "backyardchirps-venv"

# nfpm is not needed on anyone's machine: this runs it from its own image when the binary
# is not on PATH. Pinned, because the packages it writes are what a station installs.
NFPM_IMAGE = "ghcr.io/goreleaser/nfpm:v2.43.0"

# Where update_species_data leaves the full taxonomy in a checkout. build_tarball.py stages
# from the same file, for the same reason: the repository tracks only a sample of it.
TAXONOMY_IN_CHECKOUT = REPO_ROOT / "backyardchirps/species_data/generated/taxonomy/birdnet_taxonomy.json"

REPOSITORY_URL = "https://github.com/tapia/backyardchirps"

PEP_440_LOCAL_VERSION = re.compile(r"^\+[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*$")

# What a station installs. The keyring package is not among them: it needs the archive key,
# which only the publish job has, so it is built when asked for by name and left out of a
# build that is only checking the station packages still come out.
STATION_PACKAGES = ("backyardchirps", "backyardchirps-deps", "backyardchirps-species-data")
KEYRING_PACKAGE = "backyardchirps-archive-keyring"
PACKAGES = (*STATION_PACKAGES, KEYRING_PACKAGE)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Debian packages a station installs.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "build" / "packages",
        help="where to write the .deb files (default: build/packages)",
    )
    parser.add_argument(
        "--staging-dir",
        type=Path,
        default=REPO_ROOT / "build" / "staging",
        help="where to lay the trees out (default: build/staging). Emptied first",
    )
    parser.add_argument(
        "--version-suffix",
        default="",
        help="PEP 440 local version marking a build that is not a release, for example +main.a1b2c3d",
    )
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=None,
        help="the full taxonomy to ship (default: this checkout's copy, or a fresh download)",
    )
    parser.add_argument(
        "--min-upgrade-from",
        default="",
        help="refuse an upgrade from anything older than this version (default: no gate)",
    )
    parser.add_argument(
        "--only",
        choices=PACKAGES,
        action="append",
        help="build just this package, repeatable. Its dependencies are still staged",
    )
    parser.add_argument(
        "--apt-key",
        type=Path,
        default=None,
        help=f"the exported archive public key, required to build {KEYRING_PACKAGE}",
    )
    parser.add_argument(
        "--apt-base-url",
        default="",
        help=f"the repository a station reads, required to build {KEYRING_PACKAGE}",
    )
    parser.add_argument(
        "--print-main-version",
        action="store_true",
        help="print the version a push to main publishes and exit, building nothing",
    )
    parser.add_argument(
        "--keyring-version",
        default="",
        help="version for the keyring package (default: commit count over packaging/apt)",
    )
    arguments = parser.parse_args()

    if arguments.print_main_version:
        # Printed alone, so a workflow can read it with a plain command substitution.
        print(main_build_version())
        return

    wanted = tuple(arguments.only) if arguments.only else STATION_PACKAGES
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    staging = arguments.staging_dir.resolve()

    versions = {
        "APP_VERSION": _app_version(arguments.version_suffix),
        "DEPS_VERSION": _deps_version(),
        "DATA_VERSION": _data_version(),
        "KEYRING_VERSION": arguments.keyring_version or _keyring_version(),
    }
    _say(f"app {versions['APP_VERSION']}, deps {versions['DEPS_VERSION']}, data {versions['DATA_VERSION']}")

    shutil.rmtree(staging, ignore_errors=True)

    if KEYRING_PACKAGE in wanted:
        _stage_keyring(staging, arguments.apt_key, arguments.apt_base_url)
    if "backyardchirps-deps" in wanted or "backyardchirps" in wanted:
        # Staged first either way: the app package's collectstatic step runs inside this
        # same image, so the venv has to exist before the app tree can be finished.
        _stage_deps(staging)
    if "backyardchirps" in wanted:
        _stage_app(staging, versions["APP_VERSION"])
        _stage_maintainer_scripts(staging, arguments.min_upgrade_from)
    taxonomy_fetched, taxonomy_sha256 = "", ""
    if "backyardchirps-species-data" in wanted:
        taxonomy_fetched, taxonomy_sha256 = _stage_species_data(staging, arguments.taxonomy)

    environment = {
        **versions,
        "STAGING_APP": str(staging / "app"),
        "STAGING_DEPS": str(staging / "deps"),
        "STAGING_DATA": str(staging / "species-data"),
        "STAGING_KEYRING": str(staging / "keyring"),
        "SCRIPTS": str(staging / "scripts"),
        "TAXONOMY_FETCHED": taxonomy_fetched,
        "TAXONOMY_SHA256": taxonomy_sha256,
        "RELEASED": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "CHANGELOG_URL": f"{REPOSITORY_URL}/releases/tag/v{versions['APP_VERSION']}",
    }

    built = [_run_nfpm(package, environment, output_dir, staging) for package in wanted]

    for path in built:
        _say(f"wrote {path.name} ({path.stat().st_size / 1_000_000:.1f} MB)")
    print(f"APP_VERSION={versions['APP_VERSION']}")
    print(f"DEPS_VERSION={versions['DEPS_VERSION']}")
    print(f"DATA_VERSION={versions['DATA_VERSION']}")
    print(f"KEYRING_VERSION={versions['KEYRING_VERSION']}")
    print(f"PACKAGES_DIR={output_dir}")


def taxonomy_bytes(taxa: Any) -> bytes:
    """
    The taxonomy as the package stores it.

    Canonical rather than whatever bytes upstream served: sorted keys and fixed indentation,
    so that two downloads of the same data give the same file. That is what lets the nightly
    job ask "is this already published" by comparing a digest instead of rebuilding.
    """
    return json.dumps(taxa, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def taxonomy_digest(taxa: Any) -> str:
    """
    sha256 over the bytes above, which ships as a control field on the species-data package.
    """
    return hashlib.sha256(taxonomy_bytes(taxa)).hexdigest()


def main_build_version(commit_count: str | None = None, short_sha: str | None = None) -> str:
    """
    The version a push to main publishes, composed here so that only one file knows the rule.

    Two workflows need this string and neither can ask the other for it: the publish job to
    build the package, and the deploy job to install that exact version on the Pi. They each
    had their own copy of the rule, the copies drifted the moment one of them changed, and
    the deploy then spent ten minutes waiting for a version nothing had ever published.

    The commit count is what orders two builds of one release. The short sha is what a person
    can look up. Both, in that order, because a sha on its own does not sort by anything.

    Both are read from the checkout when they are not given. They are arguments at all so
    that the rule can be checked without one: the fast suite runs on a shallow clone, where
    counting commits is refused rather than answered wrongly.
    """
    return _app_version(f"+main.{commit_count or _commits_over()}.{short_sha or _head_sha()}")


def _app_version(version_suffix: str) -> str:
    """
    The version the station reports about itself, from pyproject.toml, which is also what
    goes into the dist-info the site reads.

    The same string is used as the Debian version. That works because 0.2.0+main.abc1234
    sorts above 0.2.0 in both PEP 440 and Debian ordering, and because this project only
    bumps pyproject.toml at release time. Pre-bumping it to an unreleased version would
    break that: a main build would then sort above the release it is named after, and
    stations would refuse to upgrade to the release. tests/unit/test_debian_version.py
    holds the ordering.
    """
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        version = str(tomllib.load(handle).get("project", {}).get("version", ""))
    if not version:
        _fail("Could not read the version out of pyproject.toml.")
    if not version_suffix:
        return version
    if not PEP_440_LOCAL_VERSION.match(version_suffix):
        _fail(
            "--version-suffix must be a PEP 440 local version: a + followed by letters, digits "
            f"and dots, for example +main.a1b2c3d. Got '{version_suffix}'."
        )
    return version + version_suffix


def _deps_version() -> str:
    """
    Commit count over uv.lock, so the version moves exactly when the venv's input does and
    the ordering is monotone without anybody maintaining it. Outside a git checkout it
    falls back to 1.0, which is only ever a local build.
    """
    return f"1.{_commits_over('uv.lock')}"


def _data_version() -> str:
    """
    The fetch date. The taxonomy stops living in git, so nothing in a commit can order this
    package and the day it was built is the honest answer.
    """
    return datetime.now(timezone.utc).strftime("1.%Y%m%d")


def _keyring_version() -> str:
    """
    Commit count over packaging/apt, which is where the source file lives.

    The key itself is not in git, so rotating it moves nothing here. Pass --keyring-version
    when that happens, or change the source file in the same commit, which is the usual
    case since a rotation and a change of host tend to travel together.
    """
    return f"1.{_commits_over('packaging/apt')}"


def _commits_over(path: str | None = None) -> str:
    """
    How many commits have touched a path, or the whole history when no path is given, which
    is what orders the packages nothing else can order.

    A shallow clone is refused rather than counted. It answers 1 for every path, because the
    single commit it holds looks like the one that created everything, and the version would
    then never move again however often the input changed. The package would keep the version
    it already has, the pool would skip it as already published, and stations would go on
    running the old one with nothing anywhere saying so. actions/checkout defaults to
    fetch-depth 1, so this is the normal state of a CI checkout and not an exotic case.
    """
    shallow = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if shallow.returncode == 0 and shallow.stdout.strip() == "true":
        _fail(
            f"Refusing to build: this is a shallow clone, so the commit count over "
            f"{path or 'the whole history'} is meaningless and the version would never move. "
            "Check out with fetch-depth: 0."
        )
    counted = subprocess.run(
        ["git", "rev-list", "--count", "HEAD", *(["--", path] if path else [])],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return "0" if counted.returncode != 0 else counted.stdout.strip()


def _head_sha() -> str:
    """
    The short sha of the commit being built.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--short=7", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        _fail("Refusing to build: could not read the commit being built.")
    return result.stdout.strip()


def _stage_deps(staging: Path) -> None:
    """
    Build the venv image and take the virtualenv out of it.
    """
    _say("building the virtualenv image (the slow part on a cold cache)")
    with tempfile.TemporaryDirectory() as context:
        # A context of two files rather than the repository, so the 80 MB of species data
        # and every clip in a working copy stay out of the docker daemon's way.
        shutil.copy2(REPO_ROOT / "pyproject.toml", Path(context) / "pyproject.toml")
        shutil.copy2(REPO_ROOT / "uv.lock", Path(context) / "uv.lock")
        _run(
            [
                "docker",
                "build",
                "--platform",
                "linux/arm64",
                "--target",
                "venv",
                "--file",
                str(PACKAGING / "Dockerfile"),
                "--tag",
                VENV_IMAGE,
                context,
            ]
        )

    _stage_licence(staging / "deps", "backyardchirps-deps")

    destination = staging / "deps" / VENV_PATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    _say("taking the virtualenv out of the image")
    container = subprocess.run(
        ["docker", "create", "--platform", "linux/arm64", VENV_IMAGE],
        capture_output=True,
        text=True,
        check=False,
    )
    if container.returncode != 0:
        _fail(f"Could not create a container to copy the virtualenv out of:\n{container.stderr}")
    container_id = container.stdout.strip()
    try:
        _run(["docker", "cp", f"{container_id}:/{VENV_PATH}", str(destination.parent)])
    finally:
        _run(["docker", "rm", "--force", container_id])


def _stage_keyring(staging: Path, apt_key: Path | None, apt_base_url: str) -> None:
    """
    The archive key and the source file that names it.

    Both are checked here rather than trusted, because a keyring package that ships an empty
    key or a source pointing at nothing would install cleanly and then break every
    apt-get update on every station at once.
    """
    if apt_key is None or not apt_base_url:
        _fail(f"Building {KEYRING_PACKAGE} needs both --apt-key and --apt-base-url.")
    if not apt_key.is_file() or apt_key.stat().st_size == 0:
        _fail(f"--apt-key {apt_key} is missing or empty.")
    if not apt_base_url.startswith("https://"):
        _fail(
            "--apt-base-url must be an https URL, so a station cannot be handed packages over "
            f"plain HTTP. Got '{apt_base_url}'."
        )

    keyring = staging / "keyring"
    _stage_licence(keyring, KEYRING_PACKAGE)
    _copy_to(apt_key, keyring / "usr/share/keyrings/backyardchirps-archive-keyring.gpg")

    _say(f"staging the apt source, pointing at {apt_base_url}")
    template = (PACKAGING / "apt" / "backyardchirps.sources").read_text(encoding="utf-8")
    source = keyring / "etc/apt/sources.list.d/backyardchirps.sources"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(Template(template).substitute(APT_BASE_URL=apt_base_url.rstrip("/")), encoding="utf-8")


def _stage_licence(tree: Path, package: str) -> None:
    """
    Every package carries the licence, at the path Debian keeps it: a person who has only
    the .deb can still read what they are allowed to do with it.
    """
    _copy_to(REPO_ROOT / "LICENSE", tree / "usr/share/doc" / package / "copyright")


def _stage_maintainer_scripts(staging: Path, min_upgrade_from: str) -> None:
    """
    Copy the maintainer scripts, writing the oldest version that may upgrade straight to
    this one into preinst.

    That value has no dpkg field: Breaks: is a statement about other packages, not about
    older versions of this one. What replaces it is a comparison on the version dpkg hands
    preinst, and the value has to be in the file, because nfpm expands environment
    variables in its own configuration and never inside a script.
    """
    scripts = staging / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    for script in (PACKAGING / "scripts").iterdir():
        text = script.read_text(encoding="utf-8")
        if script.name == "preinst":
            text, replaced = re.subn(r'(?m)^MIN_UPGRADE_FROM=""$', f'MIN_UPGRADE_FROM="{min_upgrade_from}"', text)
            if replaced != 1:
                _fail("Refusing to build: preinst has no MIN_UPGRADE_FROM line to write into.")
        (scripts / script.name).write_text(text, encoding="utf-8")
        (scripts / script.name).chmod(0o755)


def _stage_app(staging: Path, version: str) -> None:
    """
    The code, the frontend, the collected static files, and every file that says how a
    station is wired together.
    """
    app = staging / "app"

    _compile_messages()
    _stage_wheel(app / CODE_PATH, version)

    _say("staging bin/, the units, the nginx site, the defaults and the sudoers policy")
    shutil.copytree(PACKAGING / "bin", app / CODE_PATH / "bin")
    for script in (app / CODE_PATH / "bin").iterdir():
        script.chmod(0o755)

    shutil.copytree(PACKAGING / "systemd", app / UNITS_PATH)
    _copy_to(PACKAGING / "nginx" / "backyardchirps.conf", app / "etc/nginx/sites-available/backyardchirps")
    _copy_to(PACKAGING / "default" / "backyardchirps", app / "etc/default/backyardchirps")
    _copy_to(PACKAGING / "sudoers" / "backyardchirps", app / "etc/sudoers.d/backyardchirps")

    # The one file this package puts inside the venv the deps package owns. dpkg tracks
    # files rather than directories, so that is allowed and is how the code, which lives
    # outside the venv, becomes importable inside it.
    path_file = app / VENV_PATH / "lib" / f"python{PYTHON_VERSION}" / "site-packages" / "backyardchirps.pth"
    path_file.parent.mkdir(parents=True, exist_ok=True)
    path_file.write_text(f"/{CODE_PATH}\n")

    _stage_licence(app, "backyardchirps")
    _precompile(app / CODE_PATH)

    _build_frontend()
    # .prebuilt is the marker a release tarball carries so that apply.sh knows not to build
    # the frontend itself. It means nothing in a package, and it is only in the checkout at
    # all when somebody has built a tarball here, so leaving it in would make a local build
    # and a CI build hold different files.
    shutil.copytree(
        REPO_ROOT / "frontend" / "dist",
        app / SHARE_PATH / "frontend",
        ignore=shutil.ignore_patterns(".prebuilt"),
    )

    _collect_static(app / SHARE_PATH / "staticfiles")


def _stage_species_data(staging: Path, taxonomy: Path | None) -> tuple[str, str]:
    """
    The taxonomy and the photos, plus the date the taxonomy was fetched and a digest of it.

    Both ship as control fields. The date is for a person asking a station which taxonomy it
    is running; the digest is for the nightly job, which uses it to decide whether upstream
    has actually changed.
    """
    _stage_licence(staging / "species-data", "backyardchirps-species-data")

    species_data = staging / "species-data" / SHARE_PATH / "species-data"

    _say("staging the species photos")
    shutil.copytree(
        REPO_ROOT / "backyardchirps" / "species_data" / "assets" / "images",
        species_data / "assets" / "images",
    )

    source = taxonomy or (TAXONOMY_IN_CHECKOUT if TAXONOMY_IN_CHECKOUT.exists() else None)
    try:
        if source is None:
            _say("downloading the taxonomy, since this checkout has no copy of it")
            taxa = download_taxonomy()
            fetched = datetime.now(timezone.utc)
        else:
            _say(f"taking the taxonomy from {source}")
            with source.open(encoding="utf-8") as taxonomy_file:
                taxa = json.load(taxonomy_file)
            check_taxonomy(taxa)
            # The day that copy was written, not today. A station reports this field to say
            # which taxonomy it is running, and a local build is usually the older one.
            fetched = datetime.fromtimestamp(source.stat().st_mtime, timezone.utc)
    except TaxonomyDownloadError as error:
        _fail(f"Refusing to build: {error}")

    taxonomy_file_path = species_data / "taxonomy" / "birdnet_taxonomy.json"
    taxonomy_file_path.parent.mkdir(parents=True, exist_ok=True)
    taxonomy_file_path.write_bytes(taxonomy_bytes(taxa))
    digest = taxonomy_digest(taxa)
    _say(f"staged {len(taxa)} species, fetched {fetched:%Y-%m-%d}, sha256 {digest[:12]}")

    return fetched.strftime("%Y-%m-%d"), digest


def _stage_wheel(destination: Path, version: str) -> None:
    """
    Build the wheel and unpack it where the code lives, with an unversioned dist-info
    beside it.

    hatchling stays the single source of what counts as code: what the wheel holds is what
    the package holds, so [tool.hatch.build.targets.wheel] is the manifest and there is no
    second list to keep in step.
    """
    _say("building the wheel")
    with tempfile.TemporaryDirectory() as wheel_dir:
        _run(["uv", "build", "--wheel", "--out-dir", wheel_dir], working_directory=REPO_ROOT)
        wheels = list(Path(wheel_dir).glob("*.whl"))
        if len(wheels) != 1:
            _fail(f"Expected exactly one wheel, found {len(wheels)}.")
        destination.mkdir(parents=True)
        with zipfile.ZipFile(wheels[0]) as wheel:
            wheel.extractall(destination)

    dist_infos = list(destination.glob("*.dist-info"))
    if len(dist_infos) != 1:
        _fail(f"Expected exactly one dist-info in the wheel, found {len(dist_infos)}.")

    # Unversioned, because a versioned name changes every release and two of them could
    # exist side by side during the window dpkg unpacks in. importlib.metadata reads the
    # name from the part before the first dash and the version out of METADATA, so this is
    # discovered exactly as a normal installation would be.
    unversioned = destination / "backyardchirps.dist-info"
    metadata = (dist_infos[0] / "METADATA").read_text(encoding="utf-8")
    shutil.rmtree(dist_infos[0])
    unversioned.mkdir()
    (unversioned / "METADATA").write_text(_with_version(metadata, version), encoding="utf-8")


def _with_version(metadata: str, version: str) -> str:
    """
    Put the build's version into the metadata, which is where settings.VERSION reads it and
    therefore what the site shows.

    A build off main carries a local version that pyproject.toml does not, and rewriting
    this one line is cheaper than building the wheel from a patched copy of the tree. It is
    checked rather than assumed: an unrecognised METADATA fails the build.
    """
    rewritten, count = re.subn(r"(?m)^Version: .*$", f"Version: {version}", metadata, count=1)
    if count != 1:
        _fail("Refusing to build: the wheel's METADATA has no Version line.")
    return rewritten


def _compile_messages() -> None:
    """
    Compile the message catalogs on the build machine, so a station needs no gettext and an
    update stops being able to fail on it. The .mo files go into the wheel.
    """
    _say("compiling the message catalogs")
    _run(
        ["uv", "run", "python", "manage.py", "compilemessages", "--ignore", ".venv", "--ignore", "frontend"],
        working_directory=REPO_ROOT,
        environment={**os.environ, "SECRET_KEY": os.environ.get("SECRET_KEY", "build-only-secret-key")},
    )


def _build_frontend() -> None:
    """
    The package ships the frontend already built, so a station needs no Node at all.
    """
    _say("building the frontend")
    frontend = REPO_ROOT / "frontend"
    if not (frontend / "node_modules").is_dir():
        _say("installing npm dependencies (first run here, so this is the slow part)")
        _run(["npm", "ci"], working_directory=frontend)
    _run(["npm", "run", "build"], working_directory=frontend)


def _precompile(code: Path) -> None:
    """
    Compile the bytecode into the package, in the container and at the path it installs to.

    Two things follow from it. A station never writes a .pyc of its own, so `apt remove`
    takes the code directory with it instead of leaving a tree of __pycache__ that dpkg
    does not own and cannot delete. And the first start of every unit is faster, which on a
    Pi is worth having.

    unchecked-hash rather than the usual timestamp check, because a package sets the mtime
    of every file it installs and a .pyc that compares mtimes would be invalidated by that,
    on every station, on every install.
    """
    _say("compiling the bytecode")
    _run(
        [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/arm64",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--volume",
            f"{code}:/{CODE_PATH}",
            VENV_IMAGE,
            f"/{VENV_PATH}/bin/python",
            "-m",
            "compileall",
            "-q",
            "--invalidation-mode",
            "unchecked-hash",
            f"/{CODE_PATH}/backyardchirps",
        ]
    )


def _collect_static(destination: Path) -> None:
    """
    Collect the Django admin and DRF assets inside the venv image.

    Running it there rather than on the build machine means the assets come from exactly the
    Django the station will run. Collected on the machine that happens to have a dev
    environment, they could silently be a different Django's.

    It also fixes an old wart: collectstatic overwrites and never deletes, so a station
    carried assets from every release it had ever installed. As package content, dpkg
    removes what the new version no longer ships.
    """
    _say("collecting the static files")
    destination.mkdir(parents=True)
    _run(
        [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/arm64",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--volume",
            f"{REPO_ROOT}:/src:ro",
            "--volume",
            f"{destination}:/out",
            "--env",
            "SECRET_KEY=build-only-secret-key",
            "--env",
            "PYTHONPATH=/src",
            # Deliberately not the checkout: left unset, the data directory would be /src
            # and the build would read whatever .env a working copy happens to have.
            "--env",
            "BACKYARDCHIRPS_DATA_DIR=/tmp/build-data",
            "--env",
            "BACKYARDCHIRPS_STATIC_ROOT=/out",
            VENV_IMAGE,
            f"/{VENV_PATH}/bin/python",
            "-m",
            "backyardchirps.manage",
            "collectstatic",
            "--noinput",
            "--verbosity",
            "0",
        ]
    )


def _run_nfpm(package: str, environment: dict[str, str], output_dir: Path, staging: Path) -> Path:
    """
    Run nfpm over one package's YAML, from a local binary when there is one and from its
    own container otherwise, so nobody has to install it to build a package.
    """
    _say(f"packaging {package}")
    source_configuration = NFPM_DIR / f"{package}.yaml"
    if not source_configuration.exists():
        _fail(f"No nfpm configuration at {source_configuration}.")
    configuration = _rendered(source_configuration, environment, staging)

    if shutil.which("nfpm"):
        _run(
            ["nfpm", "package", "--config", str(configuration), "--packager", "deb", "--target", str(output_dir)],
            environment={**os.environ, **environment},
        )
    else:
        _run(_nfpm_in_docker(configuration, environment, output_dir, staging))

    debs = sorted(output_dir.glob(f"{package}_*.deb"), key=lambda path: path.stat().st_mtime)
    if not debs:
        _fail(f"nfpm reported success but wrote no .deb for {package}.")
    return debs[-1]


def _rendered(configuration: Path, environment: dict[str, str], staging: Path) -> Path:
    """
    Write a copy of the configuration with every ${VARIABLE} filled in.

    nfpm does expand environment variables, but not everywhere: it reaches version and the
    dependency list and leaves contents.src alone, where it would matter most. Doing the
    whole file here means one rule rather than two, and the rendered copy is left in the
    staging directory, which is the file to read when a package holds something surprising.
    """
    rendered = staging / "nfpm" / configuration.name
    rendered.parent.mkdir(parents=True, exist_ok=True)
    try:
        rendered.write_text(Template(configuration.read_text(encoding="utf-8")).substitute(environment), "utf-8")
    except KeyError as unset:
        _fail(f"{configuration.name} uses {unset}, which this build does not set.")
    return rendered


def _nfpm_in_docker(configuration: Path, environment: dict[str, str], output_dir: Path, staging: Path) -> list[str]:
    """
    The same run, in nfpm's own image.

    Three directories have to be visible: the repository, the staging tree nfpm reads every
    `contents.src` out of, and the output directory it writes to. Each is mounted at the path
    it already has, so every path in the configuration means the same thing inside and out and
    none has to be translated.

    The staging tree is usually under the repository, and so is mounted twice over without
    anybody noticing. It is not when --staging-dir points somewhere else, and then leaving it
    out means nfpm cannot even read its own rendered configuration.
    """
    command = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--workdir",
        str(REPO_ROOT),
    ]
    for mounted in _mount_points(REPO_ROOT, output_dir, staging):
        command += ["--volume", f"{mounted}:{mounted}"]
    for name, value in environment.items():
        command += ["--env", f"{name}={value}"]
    command += [
        NFPM_IMAGE,
        "package",
        "--config",
        str(configuration),
        "--packager",
        "deb",
        "--target",
        str(output_dir),
    ]
    return command


def _mount_points(*wanted: Path) -> list[Path]:
    """
    The directories to mount, with duplicates and anything already inside another dropped.

    Both matter, because docker refuses a repeated mount point and these three overlap in
    whatever combination the caller chose: a default run has the staging and output
    directories under the repository, and a test run puts one or both in a temporary
    directory somewhere else.
    """
    unique = sorted({path.resolve() for path in wanted})
    return [path for path in unique if not any(other != path and path.is_relative_to(other) for other in unique)]


def _copy_to(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _run(
    command: list[str],
    working_directory: Path | None = None,
    environment: dict[str, str] | None = None,
) -> None:
    """
    Run a command with everything it says on stderr, so stdout carries only the key=value
    lines a caller appends to its environment.
    """
    result = subprocess.run(command, cwd=working_directory, env=environment, stdout=sys.stderr, check=False)
    if result.returncode != 0:
        _fail(f"`{' '.join(command)}` failed with exit {result.returncode}. The reason is above.")


def _say(message: str) -> None:
    print(f"[packages] {message}", file=sys.stderr)


def _fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
