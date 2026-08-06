#!/usr/bin/env bash
# Install a bird recording station on a fresh Raspberry Pi.
#
#   curl -fsSL https://raw.githubusercontent.com/tapia/backyardchirps/main/install.sh | sudo bash
#
# It downloads the latest release, installs it under /opt/backyardchirps, creates
# the service user and the data directory, and brings the site up on your local
# network.
#
# Options, mostly for testing:
#
#   --tarball PATH        install this file instead of downloading a release
#   --manifest URL        read the release manifest from somewhere else
#   --data-dir DIR        where the station keeps its data (default /var/lib/backyardchirps)
#   --ignore-preflight    skip the hardware checks (a container is not a Pi)
#   --help
#
# Everything it prints also goes to /var/log/backyardchirps-install.log.
#
# It does not configure the station and does not start recording. Both are the
# setup wizard's job: open the address this prints and it takes you there.

set -euo pipefail

REPOSITORY_URL=https://github.com/tapia/backyardchirps
MANIFEST_URL="$REPOSITORY_URL/releases/latest/download/manifest.json"
INSTALL_ROOT=/opt/backyardchirps
DATA_DIR=/var/lib/backyardchirps
SERVICE_USER=backyardchirps
LOG_FILE=/var/log/backyardchirps-install.log
LOCAL_TARBALL=
IGNORE_PREFLIGHT=no

# Enough for the virtualenv, the acoustic model, the GeoModel and the release
# itself, with room to download the next release beside this one later.
REQUIRED_DISK_MB=4096

while [ $# -gt 0 ]; do
    case "$1" in
        --tarball)          LOCAL_TARBALL="$2"; shift 2 ;;
        --manifest)         MANIFEST_URL="$2"; shift 2 ;;
        --data-dir)         DATA_DIR="$2"; shift 2 ;;
        --ignore-preflight) IGNORE_PREFLIGHT=yes; shift ;;
        --help)
            sed -n '2,21p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            echo "Run with --help to see the options." >&2
            exit 1
            ;;
    esac
done

say()  { printf '\n==> %s\n' "$*"; }
info() { printf '    %s\n' "$*"; }
die() {
    printf '\nInstall failed: %s\n' "$*" >&2
    printf 'The full log is at %s\n\n' "$LOG_FILE" >&2
    exit 1
}

[ "$(id -u)" = "0" ] || die "This has to run as root. Try again with sudo."

mkdir -p "$(dirname "$LOG_FILE")"
# Everything from here on is written to the log as well as the screen, so a
# failure message can point at one file that holds the whole story.
exec > >(tee -a "$LOG_FILE") 2>&1
printf '\n===== %s =====\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# ---------------------------------------------------------------------------
# 1. Preflight
# ---------------------------------------------------------------------------
# Checked before anything is written, because a half-finished install is worse
# than one that never started.
say "Checking this machine"

if [ "$IGNORE_PREFLIGHT" = yes ]; then
    info "Hardware checks skipped."
else
    model="$(tr -d '\0' < /proc/device-tree/model 2> /dev/null || true)"
    case "$model" in
        *"Raspberry Pi 4"*|*"Raspberry Pi 5"*)
            info "$model"
            ;;
        "")
            die "This does not look like a Raspberry Pi. Supported: Pi 4 and Pi 5."
            ;;
        *)
            die "Unsupported board: $model. Supported: Pi 4 and Pi 5."
            ;;
    esac

    architecture="$(dpkg --print-architecture 2> /dev/null || true)"
    [ "$architecture" = arm64 ] \
        || die "This needs 64-bit Raspberry Pi OS. This system reports '$architecture'."

    if ! grep -qi 'raspbian\|raspberry' /etc/os-release 2> /dev/null; then
        die "This needs Raspberry Pi OS. See /etc/os-release."
    fi

    if [ ! -s /proc/asound/cards ] || grep -q 'no soundcards' /proc/asound/cards; then
        die "No sound card found, so there is nothing to record from. Plug in a USB microphone and run this again."
    fi
    info "a capture device is present"
fi

available_mb="$(df -Pm / | awk 'NR == 2 { print $4 }')"
[ "$available_mb" -ge "$REQUIRED_DISK_MB" ] \
    || die "Needs ${REQUIRED_DISK_MB} MB free on /, found ${available_mb} MB."
info "${available_mb} MB free on /"

# ---------------------------------------------------------------------------
# 2. System packages
# ---------------------------------------------------------------------------
# No Node: the release ships the frontend already built. No git: the release is a
# tarball. No TensorFlow: BirdNET 3 runs on onnxruntime, which uv installs.
say "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
    nginx curl ca-certificates zstd libportaudio2 sudo
info "nginx, curl, zstd, libportaudio2"

if ! command -v uv > /dev/null; then
    info "installing uv"
    # System-wide rather than into a home directory, because the installer, the
    # updater and any manual deploy are all different accounts.
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh > /dev/null
fi
command -v uv > /dev/null || die "uv did not install. See $LOG_FILE."
info "uv $(uv --version | awk '{ print $2 }')"

# ---------------------------------------------------------------------------
# 3. The release
# ---------------------------------------------------------------------------
say "Fetching the release"
download_dir="$(mktemp -d)"
trap 'rm -rf "$download_dir"' EXIT

if [ -n "$LOCAL_TARBALL" ]; then
    [ -f "$LOCAL_TARBALL" ] || die "No such file: $LOCAL_TARBALL"
    tarball="$LOCAL_TARBALL"
    info "using $tarball"
else
    curl -fsSL "$MANIFEST_URL" -o "$download_dir/manifest.json" \
        || die "Could not download the release manifest from $MANIFEST_URL."

    manifest="$(cat "$download_dir/manifest.json")"
    manifest_version="$(printf '%s' "$manifest" | sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
    manifest_url="$(printf '%s' "$manifest" | sed -n 's/.*"url"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
    manifest_sha256="$(printf '%s' "$manifest" | sed -n 's/.*"sha256"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
    [ -n "$manifest_url" ] || die "The manifest at $MANIFEST_URL has no download URL in it."
    info "version $manifest_version"

    tarball="$download_dir/$(basename "$manifest_url")"
    curl -fL --progress-bar "$manifest_url" -o "$tarball" \
        || die "Could not download the release from $manifest_url."

    actual_sha256="$(sha256sum "$tarball" | cut -d' ' -f1)"
    [ "$actual_sha256" = "$manifest_sha256" ] \
        || die "The download does not match its checksum. Expected $manifest_sha256, got $actual_sha256."
    info "checksum verified"
fi

# The version is the name of the directory inside the tarball, so a local file
# with any name still lands in the right place.
#
# The whole listing is read rather than piped into `head`, because `head` closing
# the pipe early kills tar with SIGPIPE, and under `set -o pipefail` that failure
# becomes the failure of the install.
tarball_listing="$(tar --zstd -tf "$tarball")" \
    || die "Could not read $tarball. It may be truncated or not a .tar.zst."
first_entry="${tarball_listing%%$'\n'*}"
release_name="${first_entry%%/*}"
VERSION="${release_name#backyardchirps-}"
[ -n "$VERSION" ] && [ "$VERSION" != "$release_name" ] \
    || die "This does not look like a backyardchirps release: the tarball holds '$release_name'."

RELEASE_DIR="$INSTALL_ROOT/releases/$VERSION"
say "Installing version $VERSION"
mkdir -p "$INSTALL_ROOT/releases"
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
tar --zstd -xf "$tarball" -C "$RELEASE_DIR" --strip-components=1

# The units and the nginx site point at the symlink rather than at the versioned
# directory, so an update is a symlink swap and not a rewrite of every file.
ln -sfn "$RELEASE_DIR" "$INSTALL_ROOT/current"
APP_DIR="$INSTALL_ROOT/current"
info "$RELEASE_DIR"

# ---------------------------------------------------------------------------
# 4. Service user and data directory
# ---------------------------------------------------------------------------
say "Creating the service user and the data directory"
bash "$APP_DIR/deploy/provision-data-dir.sh" "$DATA_DIR" --user "$SERVICE_USER" > /dev/null
info "$SERVICE_USER owns $DATA_DIR"

# ---------------------------------------------------------------------------
# 5. .env
# ---------------------------------------------------------------------------
# Written only once. Running the installer again on a configured station must not
# throw away its secret key and hostnames.
#
# This file holds only what has to exist before Django starts. The credentials for
# Telegram, xeno-canto and ipgeolocation.io are set in the wizard and stored in the
# database, so nothing here needs hand-editing.
say "Writing the environment file"
if [ -f "$DATA_DIR/.env" ]; then
    info "$DATA_DIR/.env already exists, leaving it alone"
else
    secret_key="$(head -c 48 /dev/urandom | base64 | tr -d '\n=+/')"
    host_name="$(hostname)"
    # The leading dot covers the hostname changing later. The raw address does
    # not, so a DHCP reservation is worth setting up: see the admin guide.
    lan_address="$(hostname -I 2> /dev/null | awk '{ print $1 }')"
    allowed_hosts=".local,localhost,127.0.0.1"
    [ -n "$lan_address" ] && allowed_hosts="$allowed_hosts,$lan_address"

    cat > "$DATA_DIR/.env" <<EOF
SECRET_KEY=$secret_key

DEBUG=false
ALLOWED_HOSTS=$allowed_hosts
CSRF_TRUSTED_ORIGINS=http://$host_name.local
SITE_URL=http://$host_name.local
EOF
    chown "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR/.env"
    chmod 640 "$DATA_DIR/.env"
    info "http://$host_name.local, reachable at $allowed_hosts"
fi

# ---------------------------------------------------------------------------
# 6. sudoers
# ---------------------------------------------------------------------------
# This is not the policy in docs/devel/deployment.md. That one lets a person deploy
# from a git checkout. Here root installs and the updater runs as root, so no
# human needs sudo at all.
#
# What the station does need is the web process, which runs as the service user,
# being able to restart the recorder after a settings change. Narrow on purpose:
# these four units, and only start, stop and restart.
say "Writing the sudoers policy"
cat > /etc/sudoers.d/backyardchirps <<EOF
$SERVICE_USER ALL=(ALL) NOPASSWD: \\
  /bin/systemctl restart backyardchirps-*, \\
  /bin/systemctl start backyardchirps-*, \\
  /bin/systemctl stop backyardchirps-*
EOF
chmod 440 /etc/sudoers.d/backyardchirps
visudo -cf /etc/sudoers.d/backyardchirps > /dev/null \
    || die "The sudoers file that was just written is not valid. Remove /etc/sudoers.d/backyardchirps."
info "$SERVICE_USER may restart its own units"

# ---------------------------------------------------------------------------
# 7. Build and start
# ---------------------------------------------------------------------------
say "Building and starting the station"
info "This is the slow part: Python packages and the acoustic model."
BACKYARDCHIRPS_APP_DIR="$APP_DIR" \
BACKYARDCHIRPS_DATA_DIR="$DATA_DIR" \
BACKYARDCHIRPS_SERVICE_USER="$SERVICE_USER" \
    bash "$APP_DIR/deploy/apply.sh" || die "The build failed. See $LOG_FILE."

# ---------------------------------------------------------------------------
# 8. Setup token
# ---------------------------------------------------------------------------
# The wizard trades this for an admin account, then deletes it. Its absence is what
# tells a later deploy that the station has an owner and may start recording.
say "Generating the setup token"
SETUP_TOKEN="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
printf '%s\n' "$SETUP_TOKEN" > "$DATA_DIR/setup-token"
chown "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR/setup-token"
chmod 600 "$DATA_DIR/setup-token"
info "$DATA_DIR/setup-token"

# ---------------------------------------------------------------------------
# 9. Done
# ---------------------------------------------------------------------------
site_url="$(grep '^SITE_URL=' "$DATA_DIR/.env" | cut -d= -f2-)"

cat <<EOF

===============================================================
 Your station is installed. Open it and finish setting it up:

   $site_url

 Setup token: $SETUP_TOKEN

 Keep the token. The wizard asks for it, and it is the only way
 to create the first admin account.

 It is not recording yet. A station that does not know where it
 is would match every species on earth, so the recorder starts
 when you finish the wizard, not before.

 Log:      $LOG_FILE
 Data:     $DATA_DIR
 Releases: $INSTALL_ROOT/releases
===============================================================

EOF
