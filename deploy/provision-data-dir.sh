#!/usr/bin/env bash
# Create the station's data directory and record where it is, so every later
# deploy finds the same one. Run once, during installation:
#
#   bash deploy/provision-data-dir.sh [/var/lib/backyardchirps]
#
# Everything the station accumulates lives in that directory: .env, the database,
# clips, downloaded models. It sits outside the checkout because a deploy replaces
# the checkout whole.
#
# Three things need the path and each reads it from somewhere different. The
# systemd units get it when apply.sh renders them. A deploy started by CI carries
# no environment at all, so it reads /etc/default/backyardchirps. Anything run by
# hand, manage.py included, reads the shell profile. This script sets up the last
# two; apply.sh handles the units.
#
# Safe to run again: it rewrites the file and leaves an existing profile line
# alone.

set -euo pipefail

DATA_DIR="${1:-/var/lib/backyardchirps}"
APP_USER="$(whoami)"
PROFILE="$HOME/.bashrc"

echo "[provision] Creating $DATA_DIR..."
sudo mkdir -p "$DATA_DIR"
sudo chown "$APP_USER" "$DATA_DIR"

# apply.sh refuses to deploy when this file disagrees with the directory it is
# about to use, because a CI deploy has nothing else to go on and would otherwise
# build an empty database inside the checkout.
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
