#!/usr/bin/env bash
# Assemble a release tarball from this checkout.
#
#   bash tools/build-tarball.sh --output-dir DIR
#
# This is the one place that decides what a release contains. CI calls it when a
# version tag is pushed, and tools/container/run-test.sh calls it to stage a
# tarball that never leaves the machine, so the installer can be tested against
# the same artifact a user downloads. Building it in two places would let the two
# drift, and the copy that drifts is the one that ships a secret.
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

while [ $# -gt 0 ]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            echo "Usage: build-tarball.sh [--output-dir DIR]" >&2
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
# .python-version is load-bearing: without it uv picks the newest interpreter it
# can find, so a station would run on a different Python than the one this project
# is tested against, and the birdnet2 extra has no wheels for every version.
say "staging"
cp -R \
    "$REPO_ROOT/backyardchirps" \
    "$REPO_ROOT/deploy" \
    "$REPO_ROOT/docs" \
    "$REPO_ROOT/manage.py" \
    "$REPO_ROOT/pyproject.toml" \
    "$REPO_ROOT/uv.lock" \
    "$REPO_ROOT/.python-version" \
    "$REPO_ROOT/.env.example" \
    "$REPO_ROOT/LICENSE" \
    "$REPO_ROOT/NOTICE" \
    "$REPO_ROOT/README.md" \
    "$STAGING/"

mkdir -p "$STAGING/frontend"
cp -R "$REPO_ROOT/frontend/dist" "$STAGING/frontend/dist"

# The species_data seeds travel with the code. Anything downloaded at runtime
# lives in the data directory and must not be in here.
rm -rf "$STAGING/backyardchirps/species_data/generated"
rm -rf "$STAGING/backyardchirps/species_data/assets/ebird_occurrence"
find "$STAGING" -name '__pycache__' -type d -prune -exec rm -rf {} +

# deploy.sh updates a git checkout, which a release install is not. It stays in
# the repository, where CI uses it to deploy, but shipping it here would only
# offer a user a script that cannot work for them. apply.sh, the one the installer
# and the updater actually call, is still in deploy/.
rm -f "$STAGING/deploy/deploy.sh"

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
