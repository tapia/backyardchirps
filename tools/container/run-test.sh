#!/usr/bin/env bash
# Install a release of this checkout onto a clean throwaway station and check what
# came out. The tarball is built here and never published, so nothing has to be
# tagged first.
#
#   bash tools/container/run-test.sh          build, deploy, assert, tear down
#   bash tools/container/run-test.sh --keep   leave it running to poke at
#
# The point is a machine that has never worked before. Anything that only passes
# because of state left behind by an earlier attempt fails here, which is exactly
# the class of problem an installer has.
#
# Not covered: audio, and real Pi hardware. A green run says the deploy is sound,
# not that the station records.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE=backyardchirps-test
NAME=backyardchirps-test-station
DATA_DIR=/var/lib/backyardchirps
APP_DIR=/home/station/backyardchirps
KEEP=no
[ "${1:-}" = "--keep" ] && KEEP=yes

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
die()  { printf '\n\033[1;31mFAILED: %s\033[0m\n\n' "$*" >&2; exit 1; }

if command -v podman > /dev/null; then
    RUNTIME=podman
    # podman knows what an init process needs, so it wires up cgroups itself.
    RUN_FLAGS=(--systemd=always)
elif command -v docker > /dev/null; then
    RUNTIME=docker
    # docker does not, so systemd needs the cgroup filesystem handed to it.
    RUN_FLAGS=(--privileged --tmpfs /run --tmpfs /tmp -v /sys/fs/cgroup:/sys/fs/cgroup:rw)
else
    die "Neither podman nor docker is installed. See the header of this file."
fi
info "using $RUNTIME"

cleanup() {
    if [ -n "${STAGING_DIR:-}" ]; then
        rm -rf "$STAGING_DIR"
    fi
    if [ "$KEEP" = yes ]; then
        printf '\nStill running. Look around with:\n  %s exec -it %s bash\nThen: %s rm -f %s\n\n' \
            "$RUNTIME" "$NAME" "$RUNTIME" "$NAME"
    else
        $RUNTIME rm -f "$NAME" > /dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

inside() { $RUNTIME exec "$NAME" "$@"; }
as_station() { $RUNTIME exec --user station "$NAME" bash -lc "$1"; }

say "Building the image"
$RUNTIME build -t "$IMAGE" "$REPO_ROOT/tools/container" > /dev/null
info "$IMAGE"

say "Booting a clean station"
$RUNTIME rm -f "$NAME" > /dev/null 2>&1 || true
$RUNTIME run -d --name "$NAME" "${RUN_FLAGS[@]}" "$IMAGE" > /dev/null
for _ in $(seq 30); do
    if inside systemctl is-system-running 2>/dev/null | grep -qE 'running|degraded'; then break; fi
    sleep 1
done
inside systemctl is-system-running 2>/dev/null | grep -qE 'running|degraded' \
    || die "systemd never came up. Try --keep and look at 'systemctl status'."
info "systemd is up"

say "Staging a release tarball"
# The station installs a release, not a checkout, so that is what it gets here.
# Nothing is tagged or published: tools/build-tarball.sh writes the same artifact
# CI would, into a temporary directory, and it is thrown away at the end.
#
# This is also what lets the image stay free of Node. The tarball carries a
# prebuilt frontend, so apply.sh has nothing to build.
STAGING_DIR="$(mktemp -d)"
eval "$(bash "$REPO_ROOT/tools/build-tarball.sh" --output-dir "$STAGING_DIR")"
info "$TARBALL_NAME"

say "Installing it"
# Unpacked rather than mounted, so the deploy writes its .venv inside the
# container and cannot touch the working tree it came from.
$RUNTIME exec --user station "$NAME" mkdir -p "$APP_DIR"
$RUNTIME exec -i --user station "$NAME" \
    tar --zstd -xf - -C "$APP_DIR" --strip-components=1 < "$TARBALL_PATH"
info "$APP_DIR"

# What the allowlist kept out matters as much as what it let in, and neither is
# visible once apply.sh has run.
inside test -f "$APP_DIR/frontend/dist/.prebuilt" \
    || die "The tarball carries no prebuilt frontend, so apply.sh will look for npm."
inside test ! -e "$APP_DIR/deploy/deploy.sh" \
    || die "deploy.sh is in the tarball. It updates a checkout and cannot work from a release."
inside test ! -e "$APP_DIR/.env" \
    || die "A .env is in the tarball."
info "prebuilt frontend present, deploy.sh and .env absent"

say "Provisioning the data directory"
as_station "bash $APP_DIR/deploy/provision-data-dir.sh $DATA_DIR"
inside test -f /etc/default/backyardchirps || die "/etc/default/backyardchirps was not written."
info "recorded in /etc/default/backyardchirps"

say "Writing .env"
as_station "cp $APP_DIR/.env.example $DATA_DIR/.env
            sed -i 's|^SECRET_KEY=.*|SECRET_KEY=test-only-not-a-real-key|' $DATA_DIR/.env
            sed -i 's|^SITE_URL=.*|SITE_URL=http://localhost|' $DATA_DIR/.env
            sed -i 's|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=localhost,127.0.0.1|' $DATA_DIR/.env"
info "$DATA_DIR/.env"

say "Deploying"
info "This is the slow part: uv sync and the BirdNET model download."
as_station "cd $APP_DIR && BACKYARDCHIRPS_DATA_DIR=$DATA_DIR bash deploy/apply.sh" \
    || die "apply.sh failed. Re-run with --keep and read the output above."

say "Checking what came out"
for unit in backyardchirps-web backyardchirps-recorder; do
    if inside systemctl is-active --quiet "$unit"; then
        info "$unit is active"
    else
        # The recorder is expected to fail here: there is no microphone in a
        # container. Say so rather than calling it a pass or a failure.
        if [ "$unit" = backyardchirps-recorder ]; then
            info "$unit is not running, which is expected without an audio device"
        else
            die "$unit is not running. Try --keep, then 'journalctl -u $unit'."
        fi
    fi
done

for timer in backyardchirps-update-species.timer backyardchirps-clip-disk-quota.timer; do
    inside systemctl is-enabled --quiet "$timer" || die "$timer was not enabled."
    info "$timer is enabled"
done

inside test -f "$DATA_DIR/detections.db" || die "No database was created in $DATA_DIR."
TABLES="$(inside sqlite3 "$DATA_DIR/detections.db" \
    "select count(*) from sqlite_master where type='table' and name like 'birds_recorder_%';")"
[ "$TABLES" = "4" ] || die "Expected 4 application tables in the database, found $TABLES."
info "database created with $TABLES application tables"

inside test -f "$APP_DIR/.venv/bin/python" || die "No virtualenv was built."
if inside "$APP_DIR/.venv/bin/python" -c "import tensorflow" 2> /dev/null; then
    die "TensorFlow is installed. The birdnet2 extra should stay out of a default install."
fi
info "TensorFlow absent, as it should be on a BirdNET 3 station"

STATUS="$(inside curl -s -o /dev/null -w '%{http_code}' http://localhost/ || true)"
[ "$STATUS" = "200" ] || die "nginx returned $STATUS for / rather than 200."
info "nginx serves the site"

API="$(inside curl -s -o /dev/null -w '%{http_code}' http://localhost/api/species/ || true)"
[ "$API" = "200" ] || die "The API returned $API for /api/species/ rather than 200."
info "the API answers"

printf '\n\033[1mA clean machine deployed and came up.\033[0m\n\n'
