#!/usr/bin/env bash
# Build, migrate, and (re)start everything from a release directory that is
# already on disk. This script never fetches code: whatever calls it puts the code
# there first. That is what lets a git checkout and an unpacked release tarball
# share one build path. deploy.sh is the caller today.
#
# Every step is idempotent, and nothing already serving traffic is restarted for
# a configuration it already has.
#
# Two directories matter and they are deliberately separate, so a release can be
# replaced whole without touching anything the station has collected:
#
#   APP_DIR    the code. Disposable, one per release.
#   DATA_DIR   .env, the database, clips, models, packs. Never replaced.
#
# Leaving BACKYARDCHIRPS_DATA_DIR unset points DATA_DIR at APP_DIR, which is what a
# development machine wants.

set -euo pipefail

APP_DIR="${BACKYARDCHIRPS_APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

# Per-machine settings, mainly where the data lives. Created during installation,
# outside the checkout, because the checkout is disposable once releases land.
#
# It has to be read here rather than passed in by the caller: a deploy triggered
# by CI carries none of the operator's environment, and falling back to APP_DIR
# would quietly point a migrated station at an empty database. An explicit
# BACKYARDCHIRPS_DATA_DIR still wins for this run, and the check below makes sure the file
# agrees with it.
if [ -z "${BACKYARDCHIRPS_DATA_DIR:-}" ] && [ -f /etc/default/backyardchirps ]; then
    # shellcheck disable=SC1091
    . /etc/default/backyardchirps
fi

DATA_DIR="${BACKYARDCHIRPS_DATA_DIR:-$APP_DIR}"
APP_USER="${BACKYARDCHIRPS_APP_USER:-$(whoami)}"
export PATH="$HOME/.local/bin:$PATH"

# A station with a real data directory has to record it in the file above, because
# that file is all a CI deploy has to go on. Getting this wrong is silent and
# expensive: every deploy you run by hand keeps working, and the first one CI runs
# builds an empty database in the checkout and repoints the services at it. So
# refuse to continue while the two disagree, which is cheap to fix now and not
# later.
if [ "$DATA_DIR" != "$APP_DIR" ]; then
    persisted_data_dir="$(
        unset BACKYARDCHIRPS_DATA_DIR
        if [ -f /etc/default/backyardchirps ]; then
            # shellcheck disable=SC1091
            . /etc/default/backyardchirps
        fi
        echo "${BACKYARDCHIRPS_DATA_DIR:-}"
    )"
    if [ "$persisted_data_dir" != "$DATA_DIR" ]; then
        echo "[apply] This deploy would use $DATA_DIR, but /etc/default/backyardchirps"
        echo "[apply] does not say so. A deploy started by CI reads only that file, so the"
        echo "[apply] next one would fall back to $APP_DIR and migrate an empty database"
        echo "[apply] there, leaving the real one orphaned."
        echo "[apply]"
        echo "[apply]   echo 'BACKYARDCHIRPS_DATA_DIR=$DATA_DIR' | sudo tee /etc/default/backyardchirps"
        echo "[apply]"
        echo "[apply] See docs/installation.md, step 5."
        exit 1
    fi
fi

# The app reads this to find its data. Exported so every manage.py call below
# resolves the same paths the services will.
export BACKYARDCHIRPS_DATA_DIR="$DATA_DIR"

cd "$APP_DIR"

read_env_value() {
    # Read one KEY=value out of .env without sourcing the file. An absent key is
    # not an error: it returns the empty string and the caller decides. The
    # `|| true` matters, since under `set -o pipefail` a grep that matches
    # nothing would otherwise abort the whole deploy.
    local key="$1"
    { grep -E "^${key}=" "$DATA_DIR/.env" || true; } | tail -n 1 | cut -d= -f2- | tr -d "\"'"
}

install_file() {
    # Render a deploy/ template into a system path, substituting the local user,
    # paths, and domain. Returns 0 when the destination content changed and 1
    # when it was already identical, so callers can reload a running service
    # only when there is something new for it to read.
    local source_file="$1"
    local destination="$2"
    local rendered
    rendered="$(sed \
        -e "s|APP_USER|$APP_USER|g" \
        -e "s|APP_DIR|$APP_DIR|g" \
        -e "s|__DATA_DIR__|$DATA_DIR|g" \
        -e "s|DOMAIN|$DOMAIN|g" \
        "$source_file")"
    if [ -f "$destination" ] && printf '%s\n' "$rendered" | cmp -s - "$destination"; then
        return 1
    fi
    printf '%s\n' "$rendered" | sudo tee "$destination" > /dev/null
}

echo "[apply] Checking prerequisites..."
mkdir -p "$DATA_DIR"
if [ ! -f "$DATA_DIR/.env" ]; then
    cp "$APP_DIR/.env.example" "$DATA_DIR/.env"
    echo "[apply] No .env found, so one was created at $DATA_DIR/.env."
    echo "[apply] Fill in SECRET_KEY, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS and"
    echo "[apply] SITE_URL, then run this script again."
    exit 1
fi
if ! command -v uv > /dev/null; then
    echo "[apply] uv is not installed. See docs/installation.md."
    exit 1
fi

# The nginx site is rendered for whatever host the app is configured to serve.
SITE_URL="$(read_env_value SITE_URL)"
DOMAIN="${SITE_URL#*://}"
DOMAIN="${DOMAIN%%/*}"

echo "[apply] Installing Python dependencies..."
uv sync --no-dev

# A release tarball ships frontend/dist already built by CI, marked with
# .prebuilt, so the Pi never needs Node. A git checkout has no marker and builds
# here instead.
if [ -f "$APP_DIR/frontend/dist/.prebuilt" ]; then
    echo "[apply] Using the prebuilt frontend from the release."
elif command -v npm > /dev/null; then
    echo "[apply] Building frontend..."
    cd "$APP_DIR/frontend"
    npm ci
    npm run build
    cd "$APP_DIR"
else
    echo "[apply] No prebuilt frontend and npm is not installed."
    exit 1
fi

echo "[apply] Running database migrations..."
uv run python manage.py migrate --noinput

# BirdNET 2 is an optional extra, left out of the install above because it drags in
# TensorFlow and most stations run BirdNET 3. A station set to it needs a second pass.
# This has to come after the migrations, since the setting lives in the database.
echo "[apply] Checking which acoustic model is selected..."
active_acoustic_model="$(uv run python manage.py shell -c \
    'from backyardchirps.features.settings.logic import Settings, SettingsKey
print(Settings.get(SettingsKey.ACTIVE_ACOUSTIC_MODEL))' | tail -n 1)"
if [ "$active_acoustic_model" = "birdnet_2" ]; then
    echo "[apply] BirdNET 2 is selected, so installing its extra as well..."
    uv sync --no-dev --extra birdnet2
else
    echo "[apply] BirdNET 3 is selected, so BirdNET 2 and TensorFlow stay uninstalled."
fi

echo "[apply] Collecting static files..."
uv run python manage.py collectstatic --noinput

# The recorder's acoustic model and the GeoModel location filter. Both live under
# DATA_DIR, so they survive a release swap, and both are downloaded only when
# missing or when their checksum no longer matches upstream. This runs before the
# recorder is restarted below, so the model is on disk by the time it starts.
echo "[apply] Downloading the BirdNET 3 model and GeoModel if needed..."
uv run python manage.py download_birdnet3_model

# nginx serves the SPA and the collected static files straight off disk, so it
# needs traversal into whichever directory those live in.
chmod o+x "$APP_DIR" 2>/dev/null || true

# ---------------------------------------------------------------------------
# App services
# ---------------------------------------------------------------------------
# Every unit below is installed, enabled, and started from here, so a fresh Pi
# (or a newly added unit) needs no manual systemctl work.
#
# Requires the sudoers entry from docs/installation.md.

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

echo "[apply] Enabling and restarting services..."
for daemon in "${DAEMONS[@]}"; do
    sudo systemctl enable "$daemon"
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
if [ -z "$DOMAIN" ]; then
    echo "[apply] SITE_URL is not set in .env, skipping the nginx site."
else
    echo "[apply] Installing/updating the nginx site for $DOMAIN..."
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
fi

echo "[apply] Done. Live at ${SITE_URL:-http://localhost}"
