#!/usr/bin/env bash
# Assemble a release tarball from this checkout.
#
#   bash tools/build-tarball.sh --output-dir DIR [--version-suffix +main.a1b2c3d]
#
# This is the one place that decides what a release contains. CI calls it when a
# version tag is pushed, and tools/container/run-test.sh calls it to stage a
# tarball that never leaves the machine, so the installer can be tested against
# the same artifact a user downloads. Building it in two places would let the two
# drift, and the copy that drifts is the one that ships a secret.
#
# --version-suffix marks a build that is not a release: a commit on main, built so
# a station can track it. It has to be a PEP 440 local version, meaning it starts
# with a + sign, and that is what keeps it from ever being mistaken for a release:
# no local version can equal the tag a release is cut from.
#
# Publishing is not this script's job. It writes a file and prints where it went.
#
# Output is key=value lines on stdout, progress on stderr, so a caller can do:
#
#   eval "$(bash tools/build-tarball.sh --output-dir /tmp/x)"     # locally
#   bash tools/build-tarball.sh --output-dir . >> "$GITHUB_ENV"   # in CI
#
# Paths with spaces would break both, which is why the output directory is
# expected not to have any.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$PWD"
VERSION_SUFFIX=

while [ $# -gt 0 ]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --version-suffix)
            VERSION_SUFFIX="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Usage: build-tarball.sh [--output-dir DIR] [--version-suffix +SEGMENT]" >&2
            exit 1
            ;;
    esac
done

say() { printf '[tarball] %s\n' "$*" >&2; }

mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"

# The version the release reports about itself comes from pyproject.toml, the same
# file settings.VERSION reads through the installed package metadata. CI checks it
# against the tag separately, before calling this.
VERSION="$(awk '
    /^\[project\]/ { in_project = 1; next }
    /^\[/          { in_project = 0 }
    in_project && /^version *=/ {
        gsub(/[" ]/, "")
        sub(/^version=/, "")
        print
        exit
    }
' "$REPO_ROOT/pyproject.toml")"

if [ -z "$VERSION" ]; then
    echo "Could not read the version out of pyproject.toml." >&2
    exit 1
fi

# Checked rather than trusted. A suffix that is not a PEP 440 local version could
# name anything, including a version somebody would read as a release, and it ends
# up in the package metadata that the site shows and the updater compares.
if [ -n "$VERSION_SUFFIX" ]; then
    if ! printf '%s' "$VERSION_SUFFIX" | grep -Eq '^\+[a-zA-Z0-9]+(\.[a-zA-Z0-9]+)*$'; then
        echo "--version-suffix must be a PEP 440 local version: a + followed by" >&2
        echo "letters, digits and dots, for example +main.a1b2c3d. Got '$VERSION_SUFFIX'." >&2
        exit 1
    fi
    VERSION="${VERSION}${VERSION_SUFFIX}"
fi
say "version $VERSION"

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
# A release ships the frontend already built and marked with .prebuilt, so the Pi
# never installs Node. apply.sh looks for that marker and skips its own build when
# it finds one.
#
# The build always runs, because a stale dist in a test run is worse than a slow
# one. `npm ci` is the expensive half and only repeats when node_modules is gone.
say "building the frontend"
#
# Both npm commands are pushed to stderr. Stdout carries the key=value lines a
# caller appends to its environment, and npm writing a summary there would end up
# in GITHUB_ENV.
if [ ! -d "$REPO_ROOT/frontend/node_modules" ]; then
    say "installing npm dependencies (first run here, so this is the slow part)"
    (cd "$REPO_ROOT/frontend" && npm ci >&2)
fi
(cd "$REPO_ROOT/frontend" && npm run build >&2)
touch "$REPO_ROOT/frontend/dist/.prebuilt"

# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------
RELEASE_NAME="backyardchirps-${VERSION}"
STAGING_PARENT="$(mktemp -d)"
STAGING="$STAGING_PARENT/$RELEASE_NAME"
trap 'rm -rf "$STAGING_PARENT"' EXIT
mkdir -p "$STAGING"

# An allowlist, deliberately, not a list of exclusions. Anything not named here
# stays out, so a file added to the repository root later can never leak into a
# public release by being forgotten. A .env sitting in a working copy is the case
# that matters.
#
# .python-version is deliberately absent. It pins development to one interpreter,
# but a station builds against the one apt installed, and naming a version here
# would break every install the day Raspberry Pi OS moves past it. What a station
# has to agree with is requires-python in pyproject.toml, which is a range.
say "staging"
RELEASE_PATHS=(
    backyardchirps
    deploy
    docs
    manage.py
    pyproject.toml
    uv.lock
    .env.example
    LICENSE
    NOTICE
    README.md
)

# Check the whole list before copying any of it. Every path here has to be tracked
# in git, not merely present in whoever's working copy: a file that is git-ignored
# builds a release fine on the machine that has it and fails on a clean checkout,
# which is CI and nowhere a person would notice. .python-version was once exactly
# that, ignored by the stock Python template while the allowlist depended on it.
for release_path in "${RELEASE_PATHS[@]}"; do
    if [ ! -e "$REPO_ROOT/$release_path" ]; then
        echo "Refusing to build: $release_path is in the release allowlist but not in this checkout." >&2
        echo "If it exists on your machine, it is git-ignored. Track it or take it off the list." >&2
        exit 1
    fi
done

cp -R "${RELEASE_PATHS[@]/#/$REPO_ROOT/}" "$STAGING/"

# The suffix has to reach the staged pyproject.toml, not just the file names.
# settings.VERSION reads the installed package metadata, which uv sync writes from
# this file, and that is what the server status page shows. Renaming the tarball
# alone would give a station three builds on disk that all call themselves the same
# version, so nothing on the site could say which one is running.
#
# Only the staged copy is touched. The one in the repository is never written to,
# which is what keeps this from becoming a way to change a release's version.
if [ -n "$VERSION_SUFFIX" ]; then
    say "marking the staged pyproject.toml as $VERSION"
    # Written with awk rather than sed -i, which takes a different argument on
    # macOS than on Linux, and this script has to run on both.
    awk -v new_version="$VERSION" '
        /^\[project\]/ { in_project = 1; print; next }
        /^\[/          { in_project = 0 }
        in_project && !written && /^version *=/ {
            print "version = \"" new_version "\""
            written = 1
            next
        }
        { print }
    ' "$STAGING/pyproject.toml" > "$STAGING/pyproject.toml.new"
    mv "$STAGING/pyproject.toml.new" "$STAGING/pyproject.toml"
    if ! grep -q "^version = \"$VERSION\"$" "$STAGING/pyproject.toml"; then
        echo "Refusing to build: could not write the version into the staged pyproject.toml." >&2
        echo "The version line is not in the shape this expected. Check it by hand." >&2
        exit 1
    fi
fi

mkdir -p "$STAGING/frontend"
cp -R "$REPO_ROOT/frontend/dist" "$STAGING/frontend/dist"

# The species_data seeds travel with the code. Anything downloaded at runtime
# lives in the data directory and must not be in here.
rm -rf "$STAGING/backyardchirps/species_data/generated"
rm -rf "$STAGING/backyardchirps/species_data/assets/ebird_occurrence"
find "$STAGING" -name '__pycache__' -type d -prune -exec rm -rf {} +
# A release carries the .po a translator edits and never the .mo compiled from it,
# which apply.sh builds on the station. A developer's checkout usually has one, and
# shipping it would mean a release could disagree with its own source.
find "$STAGING" -name '*.mo' -delete

# Refuse to build anything carrying secrets or local state, however it got there.
# A release is public and permanent, so this fails rather than trusting the copy
# step above to be right.
for forbidden in .env .coverage CLAUDE.md coverage.xml db.sqlite3 detections.db; do
    if [ -e "$STAGING/$forbidden" ]; then
        echo "Refusing to build: $forbidden is in the release." >&2
        exit 1
    fi
done
if find "$STAGING" -name '.env' -o -name '*.db' -o -name '.claude' | grep -q .; then
    echo "Refusing to build: found a .env, a database, or .claude in the tree." >&2
    find "$STAGING" -name '.env' -o -name '*.db' -o -name '.claude' >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------
TARBALL_NAME="${RELEASE_NAME}.tar.zst"
TARBALL_PATH="$OUTPUT_DIR/$TARBALL_NAME"
# COPYFILE_DISABLE stops the tar on macOS from writing a ._name AppleDouble file
# next to every entry to carry its extended attributes. Those files are noise
# inside a release, and the first one sorts ahead of the real directory, so
# anything reading the listing to find the release name sees them first. Linux
# tar ignores the variable, so CI is unaffected.
COPYFILE_DISABLE=1 tar --zstd -cf "$TARBALL_PATH" -C "$STAGING_PARENT" "$RELEASE_NAME"

if command -v sha256sum > /dev/null; then
    SHA256="$(sha256sum "$TARBALL_PATH" | cut -d' ' -f1)"
else
    # macOS has no sha256sum, and a developer staging a tarball locally is on one.
    SHA256="$(shasum -a 256 "$TARBALL_PATH" | cut -d' ' -f1)"
fi

say "wrote $TARBALL_PATH"

echo "VERSION=$VERSION"
echo "TARBALL_NAME=$TARBALL_NAME"
echo "TARBALL_PATH=$TARBALL_PATH"
echo "SHA256=$SHA256"
