#!/usr/bin/env bash
# Run install.sh on a clean throwaway machine and check what came out. The release
# it installs is built here and never published, so nothing has to be tagged first.
#
#   bash tools/container/run-test.sh                    build, install, assert, tear down
#   bash tools/container/run-test.sh --keep             leave it running to look at
#   bash tools/container/run-test.sh --runtime docker   pin the container runtime
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
INSTALL_ROOT=/opt/backyardchirps
APP_DIR="$INSTALL_ROOT/current"
SERVICE_USER=backyardchirps
KEEP=no
RUNTIME=

while [ $# -gt 0 ]; do
    case "$1" in
        --keep)    KEEP=yes; shift ;;
        --runtime) RUNTIME="$2"; shift 2 ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Usage: run-test.sh [--keep] [--runtime podman|docker]" >&2
            exit 1
            ;;
    esac
done

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
# Every failure message points at the install log, and on CI nobody can open a
# shell to read it, so the tail comes out here. The container may not exist yet,
# which is why this is allowed to find nothing.
die() {
    printf '\n\033[1;31mFAILED: %s\033[0m\n\n' "$*" >&2
    if [ -n "${RUNTIME:-}" ] && $RUNTIME exec "$NAME" \
            test -f /var/log/backyardchirps-install.log > /dev/null 2>&1; then
        printf -- '--- last 60 lines of /var/log/backyardchirps-install.log ---\n' >&2
        $RUNTIME exec "$NAME" tail -n 60 /var/log/backyardchirps-install.log >&2 || true
        printf -- '--- end of log ---\n\n' >&2
    fi
    exit 1
}

# Podman first when nothing is pinned: it knows what an init process needs and
# wires up cgroups itself, where docker has to be told. CI pins docker with
# --runtime, because that is the combination GitHub runners are set up for.
if [ -z "$RUNTIME" ]; then
    if command -v podman > /dev/null; then
        RUNTIME=podman
    elif command -v docker > /dev/null; then
        RUNTIME=docker
    else
        die "Neither podman nor docker is installed. See the header of this file."
    fi
fi
command -v "$RUNTIME" > /dev/null || die "$RUNTIME is not installed."

# Booting systemd under docker needs a private cgroup namespace and nothing else.
# Do not add -v /sys/fs/cgroup:/sys/fs/cgroup here: that is the cgroup v1 recipe,
# and every current host is cgroup v2 only. On v2 docker mounts a cgroup2
# filesystem rooted at the container's own cgroup, and bind-mounting the host tree
# over it leaves systemd looking at a root that is not its own, where it never
# finishes booting. That is silent apart from the boot timeout below.
case "$RUNTIME" in
    podman) RUN_FLAGS=(--systemd=always) ;;
    docker) RUN_FLAGS=(--privileged --cgroupns=private --tmpfs /run --tmpfs /run/lock --tmpfs /tmp) ;;
    *)      die "Unknown runtime '$RUNTIME'. Use podman or docker." ;;
esac
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
if ! inside systemctl is-system-running 2>/dev/null | grep -qE 'running|degraded'; then
    # Nothing the station does has run yet, so the install log this script normally
    # prints does not exist. Show what init itself said instead: on a machine where
    # the cgroup setup is wrong, that is the only place the reason appears, and
    # without it the failure reads as "systemd never came up" and nothing more.
    printf -- '\n--- container output ---\n' >&2
    $RUNTIME logs "$NAME" 2>&1 | tail -n 40 >&2 || true
    printf -- '--- systemctl status ---\n' >&2
    inside systemctl status --no-pager 2>&1 | head -n 20 >&2 || true
    printf -- '--- end ---\n\n' >&2
    die "systemd never came up. Try --keep and look at 'systemctl status'."
fi
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

say "Copying the installer and the tarball in"
# install.sh is not in the tarball: it is the file a user downloads on its own,
# before there is a release on the machine. So it comes from the checkout, which
# is what the one-line curl would fetch from the default branch.
$RUNTIME exec "$NAME" mkdir -p /tmp/install
$RUNTIME exec -i "$NAME" tee /tmp/install/install.sh < "$REPO_ROOT/install.sh" > /dev/null
$RUNTIME exec -i "$NAME" tee /tmp/install/uninstall.sh < "$REPO_ROOT/uninstall.sh" > /dev/null
$RUNTIME exec -i "$NAME" tee "/tmp/install/$TARBALL_NAME" < "$TARBALL_PATH" > /dev/null
info "/tmp/install"

say "Running the installer"
info "This is the slow part: Python packages and the BirdNET model download."
# --ignore-preflight because a container is not a Pi: there is no
# /proc/device-tree/model and no sound card. Everything after the hardware checks
# is the same code a real install runs.
inside bash /tmp/install/install.sh \
    --tarball "/tmp/install/$TARBALL_NAME" \
    --data-dir "$DATA_DIR" \
    --ignore-preflight \
    || die "install.sh failed. Re-run with --keep and read the output above."

say "Checking the layout it made"
inside test -L "$APP_DIR" || die "$APP_DIR is not a symlink, so an update could not swap releases."
release_target="$(inside readlink -f "$APP_DIR")"
case "$release_target" in
    "$INSTALL_ROOT"/releases/*) info "current -> $release_target" ;;
    *) die "current points at $release_target, which is not under $INSTALL_ROOT/releases." ;;
esac

inside test -f "$APP_DIR/frontend/dist/.prebuilt" \
    || die "The installed release carries no prebuilt frontend."
inside test ! -e "$APP_DIR/deploy/deploy.sh" \
    || die "deploy.sh is in the release. It updates a checkout and cannot work from one."

inside id "$SERVICE_USER" > /dev/null 2>&1 || die "The $SERVICE_USER user was not created."
# Captured rather than piped into grep: grep -q closes the pipe as soon as it
# matches, which kills the writer with SIGPIPE, and pipefail turns that into a
# failure of the whole check.
service_groups="$(inside id -nG "$SERVICE_USER")"
case " $service_groups " in
    *" audio "*) ;;
    *) die "$SERVICE_USER is not in the audio group, so the recorder cannot open a device." ;;
esac
owner="$(inside stat -c '%U' "$DATA_DIR")"
[ "$owner" = "$SERVICE_USER" ] \
    || die "$DATA_DIR is owned by $owner rather than $SERVICE_USER."
info "$SERVICE_USER exists, is in audio, and owns $DATA_DIR"

# The installer generates these rather than asking anyone for them, so a station
# that reaches this point is already usable without a person editing a file.
inside grep -q '^SECRET_KEY=.\{16,\}' "$DATA_DIR/.env" \
    || die "No usable SECRET_KEY was generated in $DATA_DIR/.env."
env_mode="$(inside stat -c '%a' "$DATA_DIR/.env")"
[ "$env_mode" = "640" ] || die ".env is mode $env_mode rather than 640."
token_mode="$(inside stat -c '%a' "$DATA_DIR/setup-token")"
[ "$token_mode" = "600" ] || die "The setup token is mode $token_mode rather than 600."
info "generated .env (640) and setup token (600)"

inside visudo -cf /etc/sudoers.d/backyardchirps > /dev/null \
    || die "The sudoers policy the installer wrote is not valid."
info "sudoers policy is valid"

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

inside systemctl is-active --quiet backyardchirps-web \
    || die "backyardchirps-web is not running. Try --keep, then 'journalctl -u backyardchirps-web'."
info "backyardchirps-web is active"

# The recorder is the opposite: it must NOT be running yet. A station that has not
# been through the wizard has no coordinates, and with none BirdNET matches against
# every species on earth, so it would fill the database with rubbish. apply.sh leaves
# it enabled but stopped, and the wizard starts it.
#
# This also happens to be why the container needs no capture device.
inside systemctl is-enabled --quiet backyardchirps-recorder \
    || die "backyardchirps-recorder was not enabled, so the wizard could not start it."
if inside systemctl is-active --quiet backyardchirps-recorder; then
    die "backyardchirps-recorder is recording on a station nobody has configured yet."
fi
info "backyardchirps-recorder is enabled but stopped, waiting for the wizard"

for timer in backyardchirps-update-species.timer backyardchirps-clip-disk-quota.timer; do
    inside systemctl is-enabled --quiet "$timer" || die "$timer was not enabled."
    info "$timer is enabled"
done

inside test -f "$DATA_DIR/detections.db" || die "No database was created in $DATA_DIR."
# The installer runs as root, so the migration must not have left a root-owned
# database, or the recorder would fail on its first detection.
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

# What a browser asks first: the wizard has to be reachable, and it has to say the
# station is unconfigured. If this is wrong nobody can ever set the station up, which
# is the one failure an install cannot recover from on its own.
SETUP="$(inside curl -s http://localhost/api/setup/status/ || true)"
printf '%s' "$SETUP" | grep -q '"is_complete":false' \
    || die "/api/setup/status/ does not report an unconfigured station: $SETUP"
printf '%s' "$SETUP" | grep -q '"token_required":true' \
    || die "/api/setup/status/ does not ask for the token the installer just wrote: $SETUP"
info "the setup wizard is reachable and asks for the token"

# Static files are collected into DATA_DIR and served by nginx, which runs as
# www-data and owns none of it. A 403 here means the data directory is not
# traversable; a 404 means collectstatic wrote somewhere nginx is not looking.
STATIC="$(inside curl -s -o /dev/null -w '%{http_code}' http://localhost/static/admin/css/base.css || true)"
[ "$STATIC" = "200" ] || die "nginx returned $STATIC for a collected static file rather than 200."
info "nginx serves the collected static files out of $DATA_DIR"

say "Uninstalling"
# Without --all, so it has to remove the software and keep every recording. A
# station being taken apart must not take the data with it by accident.
inside bash /tmp/install/uninstall.sh --data-dir "$DATA_DIR" > /dev/null \
    || die "uninstall.sh failed. Re-run with --keep and try it by hand."

inside test ! -e "$INSTALL_ROOT" || die "$INSTALL_ROOT survived the uninstall."
inside test ! -e /etc/systemd/system/backyardchirps-web.service \
    || die "The units survived the uninstall."
inside test ! -e /etc/nginx/sites-enabled/backyardchirps \
    || die "The nginx site survived the uninstall."
if inside systemctl is-active --quiet backyardchirps-web; then
    die "backyardchirps-web is still running after the uninstall."
fi
inside test -f "$DATA_DIR/detections.db" \
    || die "The uninstall deleted the database, and it was not asked to."
info "software removed, recordings kept"

printf '\n\033[1mA clean machine installed, came up, and uninstalled cleanly.\033[0m\n\n'
