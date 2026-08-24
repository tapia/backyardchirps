"""
Assemble a release tarball from this checkout.

  uv run --no-project python tools/build_tarball.py --output-dir DIR [--version-suffix +main.a1b2c3d]

This is the one place that decides what a release contains. CI calls it when a version tag is
pushed, and the container install test calls it to stage a tarball that never leaves the
machine, so the installer can be tested against the same artifact a user downloads. Building it
in two places would let the two drift, and the copy that drifts is the one that ships a secret.

--version-suffix marks a build that is not a release: a commit on main, built so a station can
track it. It has to be a PEP 440 local version, meaning it starts with a + sign, and that is
what keeps it from ever being mistaken for a release: no local version can equal the tag a
release is cut from.

Publishing is not this script's job. It writes a file and prints where it went.

Output is key=value lines on stdout, progress on stderr, so a caller can do:

  eval "$(uv run --no-project python tools/build_tarball.py --output-dir /tmp/x)"    # locally
  uv run --no-project python tools/build_tarball.py --output-dir . >> "$GITHUB_ENV"  # in CI

Paths with spaces would break both, which is why the output directory is expected not to have
any.

--no-project because nothing here needs the project environment: tomllib, shutil and hashlib are
all standard library. Running it under the project would resolve every dependency a station
installs, plus the dev group, to build a tarball.
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
from pathlib import Path
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT))

# Imports nothing but the standard library, which is what lets this run under --no-project.
from backyardchirps.integrations.birdnet import TaxonomyDownloadError
from backyardchirps.integrations.birdnet import check_taxonomy
from backyardchirps.integrations.birdnet import download_taxonomy

# An allowlist, deliberately, not a list of exclusions. Anything not named here stays out, so a
# file added to the repository root later can never leak into a public release by being
# forgotten. A .env sitting in a working copy is the case that matters.
RELEASE_PATHS = [
    "backyardchirps",
    "deploy",
    "docs",
    # Shipped so a station carries the installer it was installed with. deploy/update.sh
    # runs it to install the next release, rather than repeating its download, checksum
    # and unpack logic in a second place.
    "install.sh",
    "manage.py",
    "pyproject.toml",
    "uv.lock",
    ".env.example",
    "LICENSE",
    "README.md",
]

EXCLUDED_EVERYWHERE = ("__pycache__", "*.pyc", "*.mo")

# The taxonomy a release ships. The repository tracks a seed of a few hundred species, which is
# all a checkout and the test suite need, so a release has to carry the full one instead: a
# station resolves every BirdNET label through it, and a species it cannot name is a detection it
# drops. Written over the seed while staging, from the checkout's own copy when there is one and
# from upstream otherwise.
TAXONOMY_IN_RELEASE = "backyardchirps/species_data/taxonomy/birdnet_taxonomy.json"
TAXONOMY_IN_CHECKOUT = REPO_ROOT / "backyardchirps/species_data/generated/taxonomy/birdnet_taxonomy.json"

# The species_data seeds travel with the code. Anything downloaded at runtime lives in the data
# directory and must not be in here.
GENERATED_PATHS = [
    "backyardchirps/species_data/generated",
    "backyardchirps/species_data/assets/ebird_occurrence",
]

# Secrets and local state, refused however they got in. A release is public and permanent, so
# this fails rather than trusting the copy step to be right.
FORBIDDEN_AT_THE_TOP = [".env", ".coverage", "CLAUDE.md", "coverage.xml", "db.sqlite3", "detections.db"]
FORBIDDEN_ANYWHERE = {".env", ".claude"}
FORBIDDEN_SUFFIX = ".db"

PEP_440_LOCAL_VERSION = re.compile(r"^\+[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*$")


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble a release tarball from this checkout.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="where to write the tarball (default: the current directory)",
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
    arguments = parser.parse_args()

    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    version = _release_version(arguments.version_suffix)
    _say(f"version {version}")

    _build_frontend()

    release_name = f"backyardchirps-{version}"
    with tempfile.TemporaryDirectory() as staging_parent:
        _stage(Path(staging_parent) / release_name, version, arguments.version_suffix, arguments.taxonomy)
        tarball_path = _write_archive(Path(staging_parent), release_name, output_dir)

    with tarball_path.open("rb") as archive:
        checksum = hashlib.file_digest(archive, "sha256").hexdigest()

    _say(f"wrote {tarball_path}")
    print(f"VERSION={version}")
    print(f"TARBALL_NAME={tarball_path.name}")
    print(f"TARBALL_PATH={tarball_path}")
    print(f"SHA256={checksum}")


def _release_version(version_suffix: str) -> str:
    """
    The version the release reports about itself comes from pyproject.toml, the same file
    settings.VERSION reads through the installed package metadata. CI checks it against the tag
    separately, before calling this.
    """
    version = _version_in(REPO_ROOT / "pyproject.toml")
    if not version:
        _fail("Could not read the version out of pyproject.toml.")
    if not version_suffix:
        return version

    # Checked rather than trusted. A suffix that is not a PEP 440 local version could name
    # anything, including a version somebody would read as a release, and it ends up in the
    # package metadata that the site shows and the updater compares.
    if not PEP_440_LOCAL_VERSION.match(version_suffix):
        _fail(
            "--version-suffix must be a PEP 440 local version: a + followed by letters, digits "
            f"and dots, for example +main.a1b2c3d. Got '{version_suffix}'."
        )
    return version + version_suffix


def _version_in(pyproject: Path) -> str:
    with pyproject.open("rb") as handle:
        return str(tomllib.load(handle).get("project", {}).get("version", ""))


def _build_frontend() -> None:
    """
    A release ships the frontend already built and marked with .prebuilt, so the Pi never
    installs Node. apply.sh looks for that marker and skips its own build when it finds one.

    The build always runs, because a stale dist in a test run is worse than a slow one. `npm ci`
    is the expensive half and only repeats when node_modules is gone.
    """
    _say("building the frontend")
    frontend = REPO_ROOT / "frontend"
    if not (frontend / "node_modules").is_dir():
        _say("installing npm dependencies (first run here, so this is the slow part)")
        _run(["npm", "ci"], working_directory=frontend)
    _run(["npm", "run", "build"], working_directory=frontend)
    (frontend / "dist" / ".prebuilt").touch()


def _stage(staging: Path, version: str, version_suffix: str, taxonomy: Path | None) -> None:
    """
    Lay out the release under a temporary directory, exactly as it will be unpacked.
    """
    _say("staging")
    # Check the whole list before copying any of it. Every path here has to be tracked in git,
    # not merely present in whoever's working copy: a file that is git-ignored builds a release
    # fine on the machine that has it and fails on a clean checkout, which is CI and nowhere a
    # person would notice. .python-version was once exactly that, ignored by the stock Python
    # template while the allowlist depended on it.
    missing = [release_path for release_path in RELEASE_PATHS if not (REPO_ROOT / release_path).exists()]
    if missing:
        _fail(
            f"Refusing to build: {', '.join(missing)} in the release allowlist but not in this "
            "checkout. If it exists on your machine, it is git-ignored. Track it or take it off "
            "the list."
        )

    staging.mkdir(parents=True)
    for release_path in RELEASE_PATHS:
        source = REPO_ROOT / release_path
        if source.is_dir():
            shutil.copytree(source, staging / release_path, ignore=shutil.ignore_patterns(*EXCLUDED_EVERYWHERE))
        else:
            shutil.copy2(source, staging / release_path)

    for generated_path in GENERATED_PATHS:
        shutil.rmtree(staging / generated_path, ignore_errors=True)

    _stage_taxonomy(staging / TAXONOMY_IN_RELEASE, taxonomy)

    if version_suffix:
        _write_staged_version(staging / "pyproject.toml", version)

    shutil.copytree(REPO_ROOT / "frontend" / "dist", staging / "frontend" / "dist")

    _refuse_secrets(staging)


def _stage_taxonomy(staged_taxonomy: Path, taxonomy: Path | None) -> None:
    """
    Put the full taxonomy where the seed sits, so a station installs with every species
    BirdNET knows rather than the sample the repository tracks.

    A copy in the checkout is used when there is one, which is what keeps a test build from
    downloading 80 MB every time. CI has none, so a release is always built from a fresh
    download. Either way the file is checked before it goes in.
    """
    source = taxonomy or (TAXONOMY_IN_CHECKOUT if TAXONOMY_IN_CHECKOUT.exists() else None)
    try:
        if source is None:
            _say("downloading the taxonomy, since this checkout has no copy of it")
            taxa = download_taxonomy()
        else:
            if not source.exists():
                _fail(f"Refusing to build: no taxonomy at {source}.")
            _say(f"taking the taxonomy from {source}")
            with source.open(encoding="utf-8") as taxonomy_file:
                taxa = json.load(taxonomy_file)
            check_taxonomy(taxa)
    except TaxonomyDownloadError as error:
        _fail(f"Refusing to build: {error}")

    with staged_taxonomy.open("w", encoding="utf-8") as staged_file:
        json.dump(taxa, staged_file, ensure_ascii=False, indent=2)
    _say(f"staged {len(taxa)} species")


def _write_staged_version(staged_pyproject: Path, version: str) -> None:
    """
    The suffix has to reach the staged pyproject.toml, not just the file names.
    settings.VERSION reads the installed package metadata, which uv sync writes from this file,
    and that is what the server status page shows. Renaming the tarball alone would give a
    station three builds on disk that all call themselves the same version, so nothing on the
    site could say which one is running.

    Only the staged copy is touched. The one in the repository is never written to, which is
    what keeps this from becoming a way to change a release's version.
    """
    _say(f"marking the staged pyproject.toml as {version}")
    text = staged_pyproject.read_text()

    project_header = re.search(r"(?m)^\[project\]$", text)
    if project_header is None:
        _fail("Refusing to build: the staged pyproject.toml has no [project] table.")

    # Bounded by the next table header, so a version belonging to another table can never be the
    # one that gets rewritten.
    below_header = text[project_header.end() :]
    next_header = re.search(r"(?m)^\[", below_header)
    end_of_table = next_header.start() if next_header else len(below_header)
    project_table, rewritten = re.subn(
        r"(?m)^version *=.*$",
        f'version = "{version}"',
        below_header[:end_of_table],
        count=1,
    )
    if rewritten != 1:
        _fail("Refusing to build: the [project] table has no version line. Check it by hand.")

    staged_pyproject.write_text(text[: project_header.end()] + project_table + below_header[end_of_table:])

    # Read back with a TOML parser rather than a pattern, so this proves the file still parses
    # and says what it was meant to say.
    if _version_in(staged_pyproject) != version:
        _fail("Refusing to build: could not write the version into the staged pyproject.toml.")


def _refuse_secrets(staging: Path) -> None:
    for forbidden in FORBIDDEN_AT_THE_TOP:
        if (staging / forbidden).exists():
            _fail(f"Refusing to build: {forbidden} is in the release.")

    found = sorted(
        str(path.relative_to(staging))
        for path in staging.rglob("*")
        if path.name in FORBIDDEN_ANYWHERE or path.suffix == FORBIDDEN_SUFFIX
    )
    if found:
        _fail("Refusing to build: found a .env, a database, or .claude in the tree:\n" + "\n".join(found))


def _write_archive(staging_parent: Path, release_name: str, output_dir: Path) -> Path:
    """
    Through tar rather than through Python, which gets zstd in 3.14 and this has to run on 3.13.

    COPYFILE_DISABLE stops the tar on macOS from writing a ._name AppleDouble file next to every
    entry to carry its extended attributes. Those files are noise inside a release, and the first
    one sorts ahead of the real directory, so anything reading the listing to find the release
    name sees them first. Linux tar ignores the variable, so CI is unaffected.
    """
    tarball_path = output_dir / f"{release_name}.tar.zst"
    _run(
        ["tar", "--zstd", "-cf", str(tarball_path), "-C", str(staging_parent), release_name],
        environment={**os.environ, "COPYFILE_DISABLE": "1"},
    )
    return tarball_path


def _run(
    command: list[str],
    working_directory: Path | None = None,
    environment: dict[str, str] | None = None,
) -> None:
    """
    Run a command with everything it says on stderr. Stdout carries the key=value lines a caller
    appends to its environment, and npm writing a summary there would end up in GITHUB_ENV.
    """
    result = subprocess.run(command, cwd=working_directory, env=environment, stdout=sys.stderr, check=False)
    if result.returncode != 0:
        _fail(f"`{' '.join(command)}` failed with exit {result.returncode}. The reason is above.")


def _say(message: str) -> None:
    print(f"[tarball] {message}", file=sys.stderr)


def _fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
