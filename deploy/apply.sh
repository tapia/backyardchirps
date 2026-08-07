#!/usr/bin/env bash
# Build, migrate, and (re)start everything from a release directory that is
# already on disk. This script never fetches code: whatever calls it puts the code
# there first. install.sh is the caller today, and the updater will be the second.
#
# It runs as root against an unpacked release, and only that. Deploying from a git
# checkout was a third shape this script used to carry, and carrying it meant
# branching on who was running and on whether the data lived inside the code, in
# almost every step. Keeping one shape is what makes the rest of this file linear.
# See docs/devel/deployment.md for how to put a build on your own Pi.
#
# Every step is idempotent, and nothing already serving traffic is restarted for
# a configuration it already has.
#
# Two directories matter and they are deliberately separate, so a release can be
# replaced whole without touching anything the station has collected:
#
#   APP_DIR    the code. Disposable, one per release.
#   DATA_DIR   .env, the database, clips, models, packs. Never replaced.

set -euo pipefail

if [ "$(id -u)" != 0 ]; then
    echo "[apply] This has to run as root. It installs systemd units and an nginx"
    echo "[apply] site, and drops to the service user for everything that touches"
    echo "[apply] the data directory."
    exit 1
fi

APP_DIR="${BACKYARDCHIRPS_APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# The path the units and the nginx site are written to point at, which is a symlink
# the caller keeps: /opt/backyardchirps/current. APP_DIR is the versioned directory
# being built. They differ for exactly as long as this script takes, and the swap
# below is what makes the new release live.
#
# Splitting them is what lets a failed deploy leave nothing behind. Build first,
# point the symlink at it second: anything that goes wrong above the swap leaves the
# previous release both installed and still pointed at, so the station survives a
# restart it would otherwise not have.
#
# Equal when the caller keeps no symlink, which is the single-directory case.
LINK_DIR="${BACKYARDCHIRPS_LINK_DIR:-$APP_DIR}"

# Where the data lives, recorded at install time. An explicit BACKYARDCHIRPS_DATA_DIR
# wins for this run, which is how install.sh passes a non-default directory before
# there is anything to read.
if [ -z "${BACKYARDCHIRPS_DATA_DIR:-}" ] && [ -f /etc/default/backyardchirps ]; then
    # shellcheck disable=SC1091
    . /etc/default/backyardchirps
fi
DATA_DIR="${BACKYARDCHIRPS_DATA_DIR:-}"
if [ -z "$DATA_DIR" ]; then
    echo "[apply] Nothing says where this station keeps its data. Either"
    echo "[apply] /etc/default/backyardchirps records it or BACKYARDCHIRPS_DATA_DIR is set."
    echo "[apply] install.sh writes that file through provision-data-dir.sh."
    exit 1
fi

# The units run as this account and it owns everything under DATA_DIR, so a
# station's database and clips have one owner whatever put them there. Anything
# below that writes to DATA_DIR goes through run_as_service_user.
SERVICE_USER="${BACKYARDCHIRPS_SERVICE_USER:-backyardchirps}"
if ! id "$SERVICE_USER" > /dev/null 2>&1; then
    echo "[apply] There is no $SERVICE_USER account to own $DATA_DIR, so the services"
    echo "[apply] could not write to what this deploy is about to build."
    echo "[apply]"
    echo "[apply]   bash $APP_DIR/deploy/provision-data-dir.sh $DATA_DIR --user $SERVICE_USER"
    exit 1
fi
export PATH="$HOME/.local/bin:$PATH"

# Build against the interpreter apt installed, never one uv downloaded for itself.
# Raspberry Pi OS trixie ships Python 3.13, which is what this project asks for, so
# there is nothing to download and /usr/bin/python3 is readable by every account on
# the machine, the service user included.
#
# A downloaded interpreter would land in the home directory of whoever ran the
# deploy, where the service user cannot follow, and every unit would die at boot
# around a virtualenv built on a Python it is not allowed to open. Refusing the
# download makes that impossible rather than working around it.
export UV_PYTHON_DOWNLOADS=never

# The app reads this to find its data. Exported so every manage.py call below
# resolves the same paths the services will.
export BACKYARDCHIRPS_DATA_DIR="$DATA_DIR"

cd "$APP_DIR"

run_as_service_user() {
    sudo -u "$SERVICE_USER" "$@"
}

run_manage() {
    run_as_service_user env BACKYARDCHIRPS_DATA_DIR="$DATA_DIR" \
        "$APP_DIR/.venv/bin/python" manage.py "$@"
}

install_file() {
    local source_file="$1"
    local destination="$2"
    local rendered
    rendered="$(sed \
        -e "s|SERVICE_USER|$SERVICE_USER|g" \
        -e "s|APP_DIR|$LINK_DIR|g" \
        -e "s|__DATA_DIR__|$DATA_DIR|g" \
        "$source_file")"
    if [ -f "$destination" ] && printf '%s\n' "$rendered" | cmp -s - "$destination"; then
        return 1
    fi
    printf '%s\n' "$rendered" | sudo tee "$destination" > /dev/null
}

echo "[apply] Checking prerequisites..."
# This script builds and starts a station. It does not create one: install.sh and
# provision-data-dir.sh do that. Two scripts creating the data directory meant two
# places could disagree about who owns it, which is the one mistake here that
# costs a station its recordings.
#
# Tested through the service user, since .env is readable only by it.
for required in "$DATA_DIR" "$DATA_DIR/.env"; do
    if ! run_as_service_user test -e "$required"; then
        echo "[apply] $required does not exist, so this station has not been set up yet."
        echo "[apply] A fresh machine is set up by install.sh."
        exit 1
    fi
done
# Kept even though install.sh sets it too: the data directory is traversable so
# nginx can serve static files out of it, so .env has to protect itself.
run_as_service_user chmod 640 "$DATA_DIR/.env"
if ! command -v uv > /dev/null; then
    echo "[apply] uv is not installed. install.sh installs it."
    exit 1
fi

echo "[apply] Installing Python dependencies..."
# The two `uv sync` lines in this script are the only things that decide what is
# installed. Every `uv run` below passes --no-sync so it uses the environment
# rather than building its own: a bare `uv run` re-syncs with the dev group, and
# dev asks for the birdnet2 extra, which would drag TensorFlow onto a station that
# just took care to leave it out.
uv sync --no-dev

# Two accounts have to get into APP_DIR: nginx, which serves the built frontend and
# the collected static files straight off disk, and the service user, which reaches
# .venv. Being readable is not enough without traversal, and this has to happen
# before the check below rather than next to the nginx setup much further down.
chmod o+x "$APP_DIR" 2>/dev/null || true

# Every unit starts this interpreter as the service user, so prove it can before
# the deploy reports success. The failure this used to catch, uv building the
# virtualenv around a downloaded Python inside somebody's home directory, cannot
# happen now that UV_PYTHON_DOWNLOADS is never. Kept because it is one line and it
# catches any interpreter the units cannot reach, whatever put it there.
if ! run_as_service_user test -x "$APP_DIR/.venv/bin/python"; then
    echo "[apply] $SERVICE_USER cannot execute $APP_DIR/.venv/bin/python, which is what"
    echo "[apply] every unit starts. Check that it can traverse every directory above it."
    exit 1
fi

# A release ships frontend/dist already built, marked with .prebuilt, so no station
# ever needs Node. Its absence means this is not a release, which is the one thing
# this script cannot work with.
if [ ! -f "$APP_DIR/frontend/dist/.prebuilt" ]; then
    echo "[apply] $APP_DIR carries no prebuilt frontend, so it is not an unpacked"
    echo "[apply] release. Build one with tools/build-tarball.sh and install that."
    echo "[apply] See docs/devel/deployment.md."
    exit 1
fi
echo "[apply] Using the prebuilt frontend from the release."

echo "[apply] Running database migrations..."
run_manage migrate --noinput

# BirdNET 2 is an optional extra, left out of the install above because it drags in
# TensorFlow and most stations run BirdNET 3. A station set to it needs a second pass.
# This has to come after the migrations, since the setting lives in the database.
echo "[apply] Checking which acoustic model is selected..."
active_acoustic_model="$(run_manage shell -c \
    'from backyardchirps.features.settings.logic import Settings, SettingsKey
print(Settings.get(SettingsKey.ACTIVE_ACOUSTIC_MODEL))' | tail -n 1)"
if [ "$active_acoustic_model" = "birdnet_2" ]; then
    echo "[apply] BirdNET 2 is selected, so installing its extra as well..."
    uv sync --no-dev --extra birdnet2
else
    echo "[apply] BirdNET 3 is selected, so BirdNET 2 and TensorFlow stay uninstalled."
fi

# A station that has not been through the setup wizard has no coordinates, and with no
# coordinates BirdNET matches against every species on earth. Recording in that state
# would fill the database with rubbish before the owner has even seen the site, so the
# recorder stays stopped until the wizard finishes and starts it.
setup_complete="$(run_manage shell -c \
    'from backyardchirps.features.setup.logic import get_status
print("yes" if get_status().is_complete else "no")' | tail -n 1)"

echo "[apply] Collecting static files..."
# STATIC_ROOT is inside DATA_DIR, which the service user already owns, so this
# needs no root step to hand a directory over. The cost is that files from an
# older release are not cleaned up, since collectstatic overwrites rather than
# prunes. They are a few hundred kilobytes of Django admin assets.
run_manage collectstatic --noinput

# The recorder's acoustic model and the GeoModel location filter. Both live under
# DATA_DIR, so they survive a release swap, and both are downloaded only when
# missing or when their checksum no longer matches upstream. This runs before the
# recorder is restarted below, so the model is on disk by the time it starts.
echo "[apply] Downloading the BirdNET 3 model and GeoModel if needed..."
run_manage download_birdnet3_model

# ---------------------------------------------------------------------------
# App services
# ---------------------------------------------------------------------------
# Every unit below is installed, enabled, and started from here, so a fresh Pi
# (or a newly added unit) needs no manual systemctl work. This script is root, so
# the sudo calls below need no policy of their own. The one install.sh writes is
# for the web process, which restarts the recorder after a settings change.

# Long-running daemons: enabled at boot and restarted on every deploy so they
# pick up the new code.
DAEMONS=(backyardchirps-web backyardchirps-recorder)
# Timer-driven oneshots. Each name is both a .service (the job) and a .timer
# (the schedule); only the timer is enabled, systemd starts the service.
TIMED_JOBS=(backyardchirps-update-species backyardchirps-clip-disk-quota)

echo "[apply] Installing/updating systemd units..."
for daemon in "${DAEMONS[@]}"; do
    install_file "$APP_DIR/deploy/$daemon.service" "/etc/systemd/system/$daemon.service" || true
done
for job in "${TIMED_JOBS[@]}"; do
    install_file "$APP_DIR/deploy/$job.service" "/etc/systemd/system/$job.service" || true
    install_file "$APP_DIR/deploy/$job.timer" "/etc/systemd/system/$job.timer" || true
done
sudo systemctl daemon-reload

# ---------------------------------------------------------------------------
# Make it live
# ---------------------------------------------------------------------------
# Everything above builds and configures without changing what is running: the
# units and the nginx site point at LINK_DIR, and LINK_DIR still points at the
# release that is serving. This one line is what promotes the new one, and it is
# deliberately the last thing before the restarts.
#
# So a deploy that fails anywhere above leaves a station that is still working and
# still able to reboot, rather than one pointed at a half-built release that dies
# the next time anything restarts it.
if [ "$LINK_DIR" != "$APP_DIR" ]; then
    echo "[apply] Pointing $LINK_DIR at $APP_DIR..."
    ln -sfn "$APP_DIR" "$LINK_DIR"
fi

echo "[apply] Enabling and restarting services..."
for daemon in "${DAEMONS[@]}"; do
    sudo systemctl enable "$daemon"
    if [ "$daemon" = "backyardchirps-recorder" ] && [ "$setup_complete" != "yes" ]; then
        echo "[apply] Setup is unfinished, so the recorder stays stopped for now."
        continue
    fi
    # restart also starts a unit that was installed for the first time.
    sudo systemctl restart "$daemon"
done
for job in "${TIMED_JOBS[@]}"; do
    sudo systemctl enable --now "$job.timer"
done

# ---------------------------------------------------------------------------
# nginx
# ---------------------------------------------------------------------------
# Config changes reach the running server through a reload, never a restart,
# and only after nginx itself has validated them. If the rendered config is
# invalid the deploy fails here with the old config still serving traffic.
echo "[apply] Installing/updating the nginx site..."
nginx_config_changed=false
if install_file "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/backyardchirps; then
    nginx_config_changed=true
fi
sudo ln -sf /etc/nginx/sites-available/backyardchirps /etc/nginx/sites-enabled/backyardchirps
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t

sudo systemctl enable nginx
if ! systemctl is-active --quiet nginx; then
    sudo systemctl start nginx
elif [ "$nginx_config_changed" = true ]; then
    sudo systemctl reload nginx
fi

echo "[apply] Done."
