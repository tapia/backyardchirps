#!/usr/bin/env bash
# Install the release an admin asked for. Run as root by backyardchirps-update.service,
# which the web process may start and may not stop.
#
# The web process that launches this can be compromised, so nothing it says is trusted
# here: the version is read back from the manifest, and anything the manifest does not
# currently offer is rejected.
#
# The download, the checksum and the unpack are install.sh's, not repeated here.

set -euo pipefail

DATA_DIR="${BACKYARDCHIRPS_DATA_DIR:-/var/lib/backyardchirps}"
LINK_DIR="${BACKYARDCHIRPS_LINK_DIR:-/opt/backyardchirps/current}"
SERVICE_USER="${BACKYARDCHIRPS_SERVICE_USER:-backyardchirps}"
MANIFEST_URL="${BACKYARDCHIRPS_MANIFEST_URL:-https://github.com/tapia/backyardchirps/releases/latest/download/manifest.json}"

STATUS_DIR="$DATA_DIR/update"
STATUS_FILE="$STATUS_DIR/status.json"
BACKUP_DIR="$DATA_DIR/backups"
DATABASE="$DATA_DIR/detections.db"

# Free space needed before starting: the release beside the one running, plus its
# virtualenv. install.sh checks this too, but it does so after the download.
REQUIRED_DISK_MB=2048

VERSION=""

say() { printf '[update] %s\n' "$*"; }

# state, step, message. Written whole each time, so a reader never sees half a file.
write_status() {
    local state="$1" step="$2" message="$3" temporary
    temporary="$(mktemp "$STATUS_DIR/.status.XXXXXX")"
    python3 - "$temporary" "$state" "$VERSION" "$step" "$message" <<'PY'
import json
import sys

path, state, version, step, message = sys.argv[1:6]
with open(path, "w") as handle:
    json.dump({"state": state, "version": version, "step": step, "message": message}, handle)
PY
    chmod 644 "$temporary"
    mv "$temporary" "$STATUS_FILE"
}

fail() {
    say "FAILED: $2"
    write_status failed "$1" "$2"
    exit 1
}

manifest_field() {
    python3 -c 'import json, sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))' "$1" "$2" 2> /dev/null || true
}

mkdir -p "$STATUS_DIR"

# ---------------------------------------------------------------------------
# 1. What was asked for, and is it still on offer
# ---------------------------------------------------------------------------
write_status running checking "Reading the request"

requested="$(sudo -u "$SERVICE_USER" env BACKYARDCHIRPS_DATA_DIR="$DATA_DIR" \
    "$LINK_DIR/.venv/bin/python" "$LINK_DIR/manage.py" show_update_request 2> /dev/null | tr -d '[:space:]')"
[ -n "$requested" ] || fail checking "Nothing has been requested."

VERSION="$requested"
say "Requested: $VERSION"

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

curl -fsSL "$MANIFEST_URL" -o "$work_dir/manifest.json" \
    || fail checking "Could not read the release manifest."

published="$(manifest_field "$work_dir/manifest.json" version)"
[ "$published" = "$VERSION" ] \
    || fail checking "The manifest offers $published, not $VERSION."

# The oldest version this release can be installed over. Set by the release workflow, and
# read here rather than nowhere: update.sh runs the installer shipped with the release
# that is currently running, so a release that needs a newer installer has to say so.
minimum="$(manifest_field "$work_dir/manifest.json" min_upgrade_from)"
# Package metadata rather than the Django settings module, which will not import until
# SECRET_KEY is in the environment.
current="$("$LINK_DIR/.venv/bin/python" -c 'from importlib.metadata import version; print(version("backyardchirps"))' 2> /dev/null || true)"
if [ -n "$minimum" ] && [ -n "$current" ]; then
    # Both versions passed as arguments, never interpolated into the source.
    if ! "$LINK_DIR/.venv/bin/python" -c '
import sys
from packaging.version import Version
sys.exit(0 if Version(sys.argv[1]) >= Version(sys.argv[2]) else 1)
' "$current" "$minimum" 2> /dev/null; then
        fail checking "$VERSION cannot be installed over $current. Update by hand, see installation.md."
    fi
fi

available_mb="$(df -Pm "$LINK_DIR" | awk 'NR == 2 { print $4 }')"
[ "${available_mb:-0}" -ge "$REQUIRED_DISK_MB" ] \
    || fail checking "Needs ${REQUIRED_DISK_MB} MB free, found ${available_mb} MB."

# ---------------------------------------------------------------------------
# 2. Back up the database, because migrations run below this line
# ---------------------------------------------------------------------------
# The one step of this that cannot be undone by swapping the symlink back. A rollback
# across a migration restores this copy; see 5.3 and the admin guide.
write_status running backing-up "Backing up the database"

if [ -f "$DATABASE" ]; then
    mkdir -p "$BACKUP_DIR"
    chown "$SERVICE_USER:$SERVICE_USER" "$BACKUP_DIR"
    backup="$BACKUP_DIR/detections-before-$VERSION-$(date -u +%Y%m%dT%H%M%SZ).db"
    # SQLite's own backup API rather than cp, so a write in flight cannot leave a torn
    # file. Through python3 because the sqlite3 command line tool is not installed on a
    # station, and adding a package for one line of an update is a poor trade.
    sudo -u "$SERVICE_USER" python3 -c '
import sqlite3
import sys

source = sqlite3.connect(sys.argv[1])
destination = sqlite3.connect(sys.argv[2])
with destination:
    source.backup(destination)
destination.close()
source.close()
' "$DATABASE" "$backup" || fail backing-up "Could not back up the database."
    say "Database backed up to $backup"
else
    say "No database yet, so nothing to back up."
fi

# ---------------------------------------------------------------------------
# 3. Install it
# ---------------------------------------------------------------------------
# --ignore-preflight because this machine already passed those checks once, at install
# time, and none of what they look at can have changed: the board, the architecture, the
# OS release and whether a microphone is attached. The one preflight check that does
# matter for an update is disk space, which is why it is done above instead.
write_status running installing "Installing $VERSION"

if ! bash "$LINK_DIR/install.sh" --ignore-preflight --data-dir "$DATA_DIR" --manifest "$MANIFEST_URL"; then
    fail installing "The installer did not finish. The station is still on $current."
fi

# ---------------------------------------------------------------------------
# 4. Check it came up
# ---------------------------------------------------------------------------
write_status running verifying "Checking the station came up"

for _ in $(seq 1 30); do
    if curl -fsS --max-time 5 http://127.0.0.1/api/setup/status/ > /dev/null 2>&1; then
        write_status succeeded finished "Now running $VERSION"
        say "Done, running $VERSION"
        exit 0
    fi
    sleep 2
done

# The site is not answering on the new release. Put the old one back rather than leaving a
# station that a person has to reach over ssh to fix, and let rollback.sh own the status
# file from here: it reports what it did, including whether it had to restore the database.
say "The site did not answer on $VERSION, going back to the release before it"
if bash "$LINK_DIR/deploy/rollback.sh"; then
    exit 1
fi
fail verifying "$VERSION did not come up, and going back to the previous release failed too."
