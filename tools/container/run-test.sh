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
# `systemctl is-system-running` exits non-zero for every state except `running`,
# and `degraded` is a state this container is expected to reach: it deliberately
# removes units that want hardware it does not have. So read the state as a value
# and decide on that. Piping it into `grep -q` reads the same but is not: under
# `pipefail` the pipeline takes systemctl's exit code, so a matched `degraded`
# still counts as a failure and the boot check can never pass.
system_state=
for _ in $(seq 30); do
    system_state="$(inside systemctl is-system-running 2>/dev/null || true)"
    case "$system_state" in
        running | degraded) break ;;
    esac
    sleep 1
done
case "$system_state" in
    running | degraded) ;;
    *)
        # Nothing the station does has run yet, so the install log this script
        # normally prints does not exist. Show what init itself said instead: on a
        # machine where the cgroup setup is wrong, that is the only place the reason
        # appears, and without it the failure reads as "systemd never came up" and
        # nothing more.
        printf -- '\n--- container output ---\n' >&2
        $RUNTIME logs "$NAME" 2>&1 | tail -n 40 >&2 || true
        printf -- '--- systemctl status ---\n' >&2
        inside systemctl status --no-pager 2>&1 | head -n 20 >&2 || true
        printf -- '--- failed units ---\n' >&2
        inside systemctl list-units --failed --no-pager --no-legend 2>&1 >&2 || true
        printf -- '--- end ---\n\n' >&2
        die "systemd never came up (state: ${system_state:-none}). Try --keep and look at 'systemctl status'."
        ;;
esac
info "systemd is up (${system_state})"
if [ "$system_state" = degraded ]; then
    # Expected, and named rather than passed over: this image strips units that want
    # real hardware. Worth printing so a unit that starts failing for a new reason is
    # visible instead of hiding inside a state the test already tolerates.
    failed_units="$(inside systemctl list-units --failed --no-legend --no-pager 2>/dev/null | awk '{ print $1 }' || true)"
    info "failed units: $(printf '%s' "${failed_units:-none}" | tr '\n' ' ')"
fi

say "Staging a release tarball"
# The station installs a release, not a checkout, so that is what it gets here.
# Nothing is tagged or published: tools/build-tarball.sh writes the same artifact
# CI would, into a temporary directory, and it is thrown away at the end.
#
# This is also what lets the image stay free of Node. The tarball carries a
# prebuilt frontend, so apply.sh has nothing to build.
STAGING_DIR="$(mktemp -d)"
# Kept in a variable rather than eval'd straight from the substitution: a failing
# build inside `eval "$(...)"` sets no variables and stops nothing, so the script
# ran on and died several lines later on an unbound TARBALL_NAME, naming neither
# the build nor the reason it failed.
tarball_env="$(bash "$REPO_ROOT/tools/build-tarball.sh" --output-dir "$STAGING_DIR")" \
    || die "Building the release tarball failed. The reason is above."
eval "$tarball_env"
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

# A release carries the .po a translator edits, and gettext reads only the .mo the
# deploy compiles from it. Without this the wizard's language step would take a choice
# and every page after it would come back English.
#
# Counted rather than named, so a language added later is covered by this run without
# anybody remembering to come back here.
po_count="$(inside find "$APP_DIR/backyardchirps/locale" -name '*.po' | wc -l | tr -d ' ')"
mo_count="$(inside find "$APP_DIR/backyardchirps/locale" -name '*.mo' | wc -l | tr -d ' ')"
[ "$po_count" -gt 0 ] || die "The release carries no message catalogs at all."
[ "$mo_count" = "$po_count" ] \
    || die "$mo_count of $po_count message catalogs were compiled, so the site can only be English."
info "all $po_count message catalogs are compiled"

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

say "Re-running the installer on a station that has an owner"
# Updating is documented as re-running the installer, so this is the ordinary path and
# not an edge case. The failure it guards against is silent and total: setup completion
# is derived as "has an admin and no longer has a token", so an installer that writes a
# fresh token every time flips a configured station back to unconfigured. The router
# then sends every route to the wizard, and the wizard refuses to create a second
# admin, leaving the owner locked out of their own site.
#
# The station is given an owner the short way rather than through the wizard's HTTP
# flow, because finishing that flow needs a microphone and a recorder that can start,
# which is exactly what this container does not have. What is under test is the
# installer's decision, and that keys on the admin account and the token file alone.
as_service "BACKYARDCHIRPS_DATA_DIR=$DATA_DIR $APP_DIR/.venv/bin/python $APP_DIR/manage.py shell -c 'from backyardchirps.features.setup import queries; queries.create_superuser(\"tester\", \"TestStation2026x\")'" > /dev/null \
    || die "Could not create an admin account to test the update path with."
# What POST /api/setup/complete does once the wizard is finished.
inside rm -f "$DATA_DIR/setup-token"

SETUP="$(inside curl -s http://localhost/api/setup/status/ || true)"
printf '%s' "$SETUP" | grep -q '"is_complete":true' \
    || die "The station does not report itself configured after being given an owner: $SETUP"
info "the station now has an owner and reports setup complete"

reinstall_output="$($RUNTIME exec "$NAME" bash /tmp/install/install.sh \
    --tarball "/tmp/install/$TARBALL_NAME" \
    --data-dir "$DATA_DIR" \
    --ignore-preflight 2>&1)" \
    || die "Re-running install.sh on a configured station failed."
info "the installer ran again"

inside test ! -e "$DATA_DIR/setup-token" \
    || die "The installer wrote a setup token onto a station that already has an owner, which locks that owner out of the site."
if printf '%s' "$reinstall_output" | grep -q 'Setup token:'; then
    die "The installer offered a setup token for a station that already has an owner."
fi
SETUP="$(inside curl -s http://localhost/api/setup/status/ || true)"
printf '%s' "$SETUP" | grep -q '"is_complete":true' \
    || die "The station lost its setup state when the installer ran again: $SETUP"
info "no token written, and the station is still configured"

say "A failed build must leave the running release alone"
# The expensive half of a deploy happens before anything is switched over, so a
# build that dies has to leave the station exactly as it found it: still pointed at
# the release that works, and still able to survive a reboot. Getting this backwards
# is silent, which is what makes it worth a test: the station carries on serving from
# files it already has open, and only dies the next time anything restarts it.
#
# A release directory holding nothing but deploy/ is the cheapest way to fail. It
# gets as far as `uv sync`, which is where a real deploy is most likely to break,
# and that is above the swap.
live_release_before="$(inside readlink -f "$APP_DIR")"
inside mkdir -p "$INSTALL_ROOT/releases/9.9.9-broken"
inside cp -r "$live_release_before/deploy" "$INSTALL_ROOT/releases/9.9.9-broken/deploy"

if inside env BACKYARDCHIRPS_APP_DIR="$INSTALL_ROOT/releases/9.9.9-broken" \
        BACKYARDCHIRPS_LINK_DIR="$APP_DIR" \
        BACKYARDCHIRPS_DATA_DIR="$DATA_DIR" \
        BACKYARDCHIRPS_SERVICE_USER="$SERVICE_USER" \
        bash "$INSTALL_ROOT/releases/9.9.9-broken/deploy/apply.sh" > /dev/null 2>&1; then
    die "apply.sh reported success on a release with no code in it."
fi

live_release_after="$(inside readlink -f "$APP_DIR")"
[ "$live_release_after" = "$live_release_before" ] \
    || die "A failed build moved $APP_DIR from $live_release_before to $live_release_after, so the next restart would start a release that was never built."
inside systemctl is-active --quiet backyardchirps-web \
    || die "A failed build took the web server down with it."
inside rm -rf "$INSTALL_ROOT/releases/9.9.9-broken"
info "the symlink and the web server both survived a failed build"

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
