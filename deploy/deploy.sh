#!/usr/bin/env bash
# Pull main into the working checkout, then hand over to apply.sh, which does the
# actual work. Called by GitHub Actions on every push to main, and safe to run by
# hand:
#
#   bash ~/backyardchirps/deploy/deploy.sh
#
# This is the deploy path for a station running from a git checkout. Installing
# from a release tarball unpacks it and calls apply.sh directly instead.

set -euo pipefail

APP_DIR="${BACKYARDCHIRPS_APP_DIR:-$HOME/backyardchirps}"

cd "$APP_DIR"

echo "[deploy] Pulling latest code..."
git pull origin main

exec bash "$APP_DIR/deploy/apply.sh"
