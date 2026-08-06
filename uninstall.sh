#!/usr/bin/env bash
# Remove a bird recording station.
#
#   sudo bash uninstall.sh              stop and remove the software, keep the data
#   sudo bash uninstall.sh --all        remove the data as well
#
# The default keeps everything the station recorded: the database, the clips and
# the downloaded models stay in /var/lib/backyardchirps. Reinstalling on top of
# them picks up where it left off. --all deletes them, which cannot be undone.
#
# What it never touches: nginx, uv and the other system packages. They were
# already useful before this and may be in use by something else.

set -euo pipefail

INSTALL_ROOT=/opt/backyardchirps
DATA_DIR=/var/lib/backyardchirps
SERVICE_USER=backyardchirps
REMOVE_DATA=no

while [ $# -gt 0 ]; do
    case "$1" in
        --all)      REMOVE_DATA=yes; shift ;;
        --data-dir) DATA_DIR="$2"; shift 2 ;;
        --help)
            sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

say()  { printf '\n==> %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }

[ "$(id -u)" = "0" ] || { echo "This has to run as root. Try again with sudo." >&2; exit 1; }

if [ "$REMOVE_DATA" = yes ]; then
    printf '\nThis will delete %s, including every recording and the database.\n' "$DATA_DIR"
    printf 'There is no way to undo it. Type DELETE to continue: '
    read -r confirmation
    [ "$confirmation" = "DELETE" ] || { echo "Nothing was removed."; exit 1; }
fi

say "Stopping the station"
for unit in backyardchirps-web backyardchirps-recorder; do
    systemctl disable --now "$unit" 2> /dev/null || true
done
for timer in backyardchirps-update-species backyardchirps-clip-disk-quota; do
    systemctl disable --now "$timer.timer" 2> /dev/null || true
done

say "Removing the units"
rm -f /etc/systemd/system/backyardchirps-*.service
rm -f /etc/systemd/system/backyardchirps-*.timer
systemctl daemon-reload
info "removed"

say "Removing the nginx site"
rm -f /etc/nginx/sites-enabled/backyardchirps /etc/nginx/sites-available/backyardchirps
if systemctl is-active --quiet nginx; then
    # A reload with no site left is fine. A failed config test is not, and would
    # leave nginx serving the removed site until the next restart.
    nginx -t > /dev/null 2>&1 && systemctl reload nginx
fi
info "removed"

say "Removing the software"
rm -f /etc/sudoers.d/backyardchirps
rm -f /etc/default/backyardchirps
rm -rf "$INSTALL_ROOT"
info "$INSTALL_ROOT"

if [ "$REMOVE_DATA" = yes ]; then
    say "Removing the data"
    rm -rf "$DATA_DIR"
    # The user's home was the data directory, so it goes with it.
    userdel "$SERVICE_USER" 2> /dev/null || true
    info "$DATA_DIR and the $SERVICE_USER user"
    printf '\nEverything is gone.\n\n'
else
    printf '\nThe software is gone. Your recordings are still in %s.\n' "$DATA_DIR"
    printf 'The %s user was kept, since it owns them.\n' "$SERVICE_USER"
    printf 'Run again with --all to remove those too.\n\n'
fi
