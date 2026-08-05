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
# station deploys, backyardchirps runs. Keeping them separate here is the only way
# to catch a deploy step that quietly needs to be the same account as the services.
SERVICE_USER=backyardchirps
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
# The service user has no login shell, so it is reached through sudo rather than
# by execing as it, which is also how apply.sh reaches it.
as_service() { $RUNTIME exec "$NAME" sudo -u "$SERVICE_USER" bash -c "$1"; }

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

say "Provisioning the service user and the data directory"
as_station "bash $APP_DIR/deploy/provision-data-dir.sh $DATA_DIR --user $SERVICE_USER"
inside test -f /etc/default/backyardchirps || die "/etc/default/backyardchirps was not written."

inside id "$SERVICE_USER" > /dev/null 2>&1 || die "The $SERVICE_USER user was not created."
inside id -nG "$SERVICE_USER" | tr ' ' '\n' | grep -qx audio \
    || die "$SERVICE_USER is not in the audio group, so the recorder cannot open a device."
owner="$(inside stat -c '%U' "$DATA_DIR")"
[ "$owner" = "$SERVICE_USER" ] \
    || die "$DATA_DIR is owned by $owner rather than $SERVICE_USER."
info "$SERVICE_USER exists, is in audio, and owns $DATA_DIR"

say "Writing .env"
# As the service user, because the data directory is not world-writable any more.
# station deploys; it does not own what the station collects.
as_service "cp $APP_DIR/.env.example $DATA_DIR/.env
            sed -i 's|^SECRET_KEY=.*|SECRET_KEY=test-only-not-a-real-key|' $DATA_DIR/.env
            sed -i 's|^SITE_URL=.*|SITE_URL=http://localhost|' $DATA_DIR/.env
            sed -i 's|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=localhost,127.0.0.1|' $DATA_DIR/.env"
info "$DATA_DIR/.env"

say "Deploying"
info "This is the slow part: uv sync and the BirdNET model download."
as_station "cd $APP_DIR && BACKYARDCHIRPS_DATA_DIR=$DATA_DIR bash deploy/apply.sh" \
    || die "apply.sh failed. Re-run with --keep and read the output above."

say "Checking what came out"
# Which account a unit runs as is the whole point of the service user, and it is
# checkable whether or not the unit is healthy, so check it first.
for unit in backyardchirps-web backyardchirps-recorder \
            backyardchirps-update-species backyardchirps-clip-disk-quota; do
    unit_user="$(inside systemctl show "$unit" --property=User --value)"
    [ "$unit_user" = "$SERVICE_USER" ] \
        || die "$unit runs as '${unit_user:-the default}' rather than $SERVICE_USER."
done
info "all four units run as $SERVICE_USER"

for unit in backyardchirps-web backyardchirps-recorder; do
    if inside systemctl is-active --quiet "$unit"; then
        info "$unit is active"
    else
        # A container has no capture device, so the recorder failing is expected.
        # Failing for some other reason is not, and the old check could not tell
        # the two apart. Insist the journal says it was the audio device.
        if [ "$unit" = backyardchirps-recorder ]; then
            if inside journalctl -u "$unit" --no-pager \
                | grep -qiE 'audio|sound|device|portaudio|alsa'; then
                info "$unit stopped on the audio device, which is expected here"
            else
                die "$unit is not running, and not because of the audio device. Try --keep, then 'journalctl -u $unit'."
            fi
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
# The deploy ran as station but the migration must not have left a database only
# station can write to, or the recorder would fail on its first detection.
db_owner="$(inside stat -c '%U' "$DATA_DIR/detections.db")"
[ "$db_owner" = "$SERVICE_USER" ] \
    || die "detections.db is owned by $db_owner rather than $SERVICE_USER, so the services cannot write to it."
info "detections.db is owned by $SERVICE_USER"
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

# Static files are collected into DATA_DIR and served by nginx, which runs as
# www-data and owns none of it. A 403 here means the data directory is not
# traversable; a 404 means collectstatic wrote somewhere nginx is not looking.
STATIC="$(inside curl -s -o /dev/null -w '%{http_code}' http://localhost/static/admin/css/base.css || true)"
[ "$STATIC" = "200" ] || die "nginx returned $STATIC for a collected static file rather than 200."
info "nginx serves the collected static files out of $DATA_DIR"

printf '\n\033[1mA clean machine deployed and came up.\033[0m\n\n'
