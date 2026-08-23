#!/usr/bin/env bash
# Go back to the release installed before this one. Run as root by
# backyardchirps-rollback.service, which the web process may start and may not stop.

set -euo pipefail

DATA_DIR="${BACKYARDCHIRPS_DATA_DIR:-/var/lib/backyardchirps}"
LINK_DIR="${BACKYARDCHIRPS_LINK_DIR:-/opt/backyardchirps/current}"
RELEASES_DIR="${BACKYARDCHIRPS_RELEASES_DIR:-$(dirname "$LINK_DIR")/releases}"

STATUS_DIR="$DATA_DIR/update"
STATUS_FILE="$STATUS_DIR/status.json"
BACKUP_DIR="$DATA_DIR/backups"
DATABASE="$DATA_DIR/detections.db"

VERSION=""

say() { printf '[rollback] %s\n' "$*"; }

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

mkdir -p "$STATUS_DIR"
write_status running rolling-back "Looking for the previous release"

# Newest by modification time, excluding whatever current points at. The same ordering
# install.sh prunes by, so the two agree about which release is the one before.
leaving="$(readlink -f "$LINK_DIR")"
previous="$(
    find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d ! -path "$leaving" -printf '%T@ %p\n' 2> /dev/null \
        | sort -rn | head -1 | cut -d' ' -f2-
)"
[ -n "$previous" ] || fail rolling-back "There is no earlier release on this station to go back to."
[ -x "$previous/.venv/bin/python" ] || fail rolling-back "$previous has no virtualenv, so it cannot be started."

VERSION="$(
    "$previous/.venv/bin/python" -c 'from importlib.metadata import version; print(version("backyardchirps"))' \
        2> /dev/null || basename "$previous"
)"
say "Going back to $VERSION at $previous"

# Stop the recorder before anything else. It is the only thing that writes detections, and
# a restore below would throw away whatever it wrote after the check.
systemctl stop backyardchirps-recorder || true

ln -sfn "$previous" "$LINK_DIR"

# Asked of the release being restored, not this one: what matters is which migrations that
# code knows about. Anything the database has applied beyond them is schema the old code
# has never seen.
ahead="$(
    sudo -u "$(stat -c %U "$DATABASE" 2> /dev/null || echo root)" \
        env BACKYARDCHIRPS_DATA_DIR="$DATA_DIR" \
        "$previous/.venv/bin/python" "$previous/manage.py" show_migrations_ahead 2> /dev/null || true
)"

if [ -n "$ahead" ]; then
    say "The database is ahead of $VERSION: $(echo "$ahead" | tr '\n' ' ')"
    write_status running restoring "Restoring the database saved before the update"

    backup="$(find "$BACKUP_DIR" -maxdepth 1 -name 'detections-before-*.db' -printf '%T@ %p\n' 2> /dev/null \
        | sort -rn | head -1 | cut -d' ' -f2-)"
    [ -n "$backup" ] || fail restoring "The database is ahead of $VERSION and there is no backup to restore."

    # Kept rather than deleted. It holds every detection recorded since the update, which
    # this is about to drop, and that is not something to throw away silently.
    superseded="$BACKUP_DIR/detections-rolled-back-$(date -u +%Y%m%dT%H%M%SZ).db"
    mv "$DATABASE" "$superseded"
    cp "$backup" "$DATABASE"
    chown --reference="$superseded" "$DATABASE"
    say "Restored $backup. What it replaced is kept at $superseded."
fi

write_status running verifying "Restarting on $VERSION"
systemctl restart backyardchirps-web
systemctl start backyardchirps-recorder || true

for _ in $(seq 1 30); do
    if curl -fsS --max-time 5 http://127.0.0.1/api/setup/status/ > /dev/null 2>&1; then
        write_status succeeded finished "Back on $VERSION"
        say "Done, running $VERSION"
        exit 0
    fi
    sleep 2
done

fail verifying "The site did not answer after going back to $VERSION. Check journalctl -u backyardchirps-web."
