#!/usr/bin/env bash
# Create the service user, its data directory, and record where that directory is
# so every later deploy finds the same one. Run once, during installation:
#
#   bash deploy/provision-data-dir.sh [/var/lib/backyardchirps] [--user backyardchirps]
#
# Everything the station accumulates lives in that directory: .env, the database,
# clips, downloaded models. It sits outside the code because an update replaces the
# release whole. It is also the service user's home, which is why one script
# creates both.
#
# The services run as a dedicated system user rather than as whoever deploys, so a
# station's data has one owner no matter who last ran a deploy, and the recorder
# gets at the microphone through the audio group rather than through a login
# account. Deploys run as root and drop to this one for anything that writes to the
# data directory. See deploy/apply.sh.
#
# Three things need the path and each reads it from somewhere different. The
# systemd units get it when apply.sh renders them. apply.sh itself reads
# /etc/default/backyardchirps when its caller passes nothing. Anything run by hand,
# manage.py included, reads the shell profile. This script sets up the last two;
# apply.sh handles the units.
#
# Safe to run again: it rewrites the file, leaves an existing profile line alone,
# and leaves an existing user alone.

set -euo pipefail

DATA_DIR=/var/lib/backyardchirps
SERVICE_USER=backyardchirps
PROFILE="$HOME/.bashrc"

while [ $# -gt 0 ]; do
    case "$1" in
        --user)
            SERVICE_USER="$2"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1" >&2
            echo "Usage: provision-data-dir.sh [DATA_DIR] [--user NAME]" >&2
            exit 1
            ;;
        *)
            DATA_DIR="$1"
            shift
            ;;
    esac
done

# A system user: no password, no login shell, and a home that is the data
# directory itself. The audio group is what lets the recorder open the capture
# device without giving this account anything else.
if id "$SERVICE_USER" > /dev/null 2>&1; then
    echo "[provision] The user $SERVICE_USER already exists, leaving it as it is."
else
    echo "[provision] Creating the system user $SERVICE_USER..."
    sudo useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

if getent group audio > /dev/null; then
    sudo usermod -aG audio "$SERVICE_USER"
else
    echo "[provision] No audio group on this machine, so the recorder will not"
    echo "[provision] reach a capture device. Expected in a container, not on a Pi."
fi

echo "[provision] Creating $DATA_DIR..."
sudo mkdir -p "$DATA_DIR"
sudo chown "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"
# Traversable by everyone, because nginx serves the collected static files out of
# this directory and runs as www-data. Secrets are protected by the mode on .env
# itself, which apply.sh sets to 640, not by closing the directory. The deploying
# user still reads .env through sudo rather than through the permission bits.
sudo chmod 755 "$DATA_DIR"

# Where the updater reports progress. Root writes it and the service user only reads
# it, which is the point of the separate directory: the status file sits inside a
# directory the web process cannot write, so it cannot replace it with a symlink and
# have root follow that symlink on the next update.
echo "[provision] Creating $DATA_DIR/update..."
sudo mkdir -p "$DATA_DIR/update"
sudo chown root:root "$DATA_DIR/update"
sudo chmod 755 "$DATA_DIR/update"

# This is what apply.sh reads when its caller passes no data directory, so a person
# running it by hand on the station gets the same one the units use.
echo "[provision] Recording it in /etc/default/backyardchirps..."
printf 'BACKYARDCHIRPS_DATA_DIR=%s\n' "$DATA_DIR" | sudo tee /etc/default/backyardchirps > /dev/null

if grep -qs '^export BACKYARDCHIRPS_DATA_DIR=' "$PROFILE"; then
    echo "[provision] $PROFILE already exports BACKYARDCHIRPS_DATA_DIR, leaving it as it is."
    echo "[provision] Check it says $DATA_DIR."
else
    echo "[provision] Adding the export to $PROFILE..."
    printf 'export BACKYARDCHIRPS_DATA_DIR=%s\n' "$DATA_DIR" >> "$PROFILE"
fi

echo "[provision] Done. This shell does not have it yet, so either open a new one"
echo "[provision] or run:"
echo
echo "    export BACKYARDCHIRPS_DATA_DIR=$DATA_DIR"
