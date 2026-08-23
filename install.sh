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
#   --preflight-only      run the hardware checks and stop, installing nothing
#   --print-sudoers       print the sudoers policy and stop, installing nothing
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
PREFLIGHT_ONLY=no
PRINT_SUDOERS=no

# Preflight looks at the machine through these four values. They are overridable so the
# checks can be run against fixtures, which is the only way to exercise them: the
# container test is not a Raspberry Pi, and the one machine that is cannot be a test
# fixture. See tests/unit/test_preflight.py.
DEVICE_TREE_MODEL_FILE="${DEVICE_TREE_MODEL_FILE:-/proc/device-tree/model}"
OS_RELEASE_FILE="${OS_RELEASE_FILE:-/etc/os-release}"
ASOUND_PCM_FILE="${ASOUND_PCM_FILE:-/proc/asound/pcm}"
RPI_ISSUE_FILE="${RPI_ISSUE_FILE:-/etc/rpi-issue}"
SYSTEM_ARCHITECTURE="${SYSTEM_ARCHITECTURE:-$(dpkg --print-architecture 2> /dev/null || true)}"

# Enough for the virtualenv, the acoustic model, the GeoModel and the release
# itself, with room to download the next release beside this one later.
REQUIRED_DISK_MB=4096

# How many release directories to leave under releases/. Two would be enough to
# roll back once; three leaves room to roll back from a rollback.
KEEP_RELEASES=3

# The units the web process may control through sudo, and the verbs it may use on
# them. Section 7 writes the policy from these two lists, and
# tests/unit/test_sudoers_policy.py fails if they stop matching what the code asks for.
MANAGED_UNITS=(
    backyardchirps-web
    backyardchirps-recorder
    backyardchirps-update-species
    backyardchirps-clip-disk-quota
)
MANAGED_UNIT_VERBS=(start stop restart)

while [ $# -gt 0 ]; do
    case "$1" in
        --tarball)          LOCAL_TARBALL="$2"; shift 2 ;;
        --manifest)         MANIFEST_URL="$2"; shift 2 ;;
        --data-dir)         DATA_DIR="$2"; shift 2 ;;
        --ignore-preflight) IGNORE_PREFLIGHT=yes; shift ;;
        --preflight-only)   PREFLIGHT_ONLY=yes; shift ;;
        --print-sudoers)    PRINT_SUDOERS=yes; shift ;;
        --help)
            # The help text is the comment block between the shebang and the first line
            # of code, so editing that block also updates --help.
            awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"
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

# One value out of /etc/os-release. Parsed rather than sourced, because that file
# sets NAME, VERSION and ID, and VERSION is this script's own variable for the
# release being installed. Missing file or missing key gives an empty string, which
# the caller checks for.
read_os_release() {
    awk -F= -v key="$1" '
        $1 == key {
            value = substr($0, length(key) + 2)
            gsub(/^"|"$/, "", value)
            print value
            exit
        }
    ' "$OS_RELEASE_FILE" 2> /dev/null || true
}
die() {
    printf '\nInstall failed: %s\n' "$*" >&2
    printf 'The full log is at %s\n\n' "$LOG_FILE" >&2
    exit 1
}

# One field out of the release manifest. The manifest is JSON, and the order of its
# fields is not fixed, so read it with a JSON parser rather than a regex. python3 is
# installed before this is first called. A missing file or missing key gives an empty
# string, which the caller checks for.
read_manifest_field() {
    python3 -c 'import json, sys; print(json.load(open(sys.argv[1])).get(sys.argv[2], ""))' \
        "$1" "$2" 2> /dev/null || true
}

# The one-time token the wizard trades for the first admin account. Sets SETUP_TOKEN so
# the summary at the end can print it, since the file itself is only readable by the
# service user.
write_setup_token() {
    SETUP_TOKEN="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    printf '%s\n' "$SETUP_TOKEN" > "$DATA_DIR/setup-token"
    chown "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR/setup-token"
    chmod 600 "$DATA_DIR/setup-token"
}

# Checked before anything is written, because a half-finished install is worse than
# one that never started. A function rather than a straight run of statements so
# --preflight-only can call it on a machine that is not a Pi, against fixtures.
check_this_machine() {
    say "Checking this machine"

    if [ "$IGNORE_PREFLIGHT" = yes ]; then
        info "Hardware checks skipped."
    else
        model="$(tr -d '\0' < "$DEVICE_TREE_MODEL_FILE" 2> /dev/null || true)"
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

        [ "$SYSTEM_ARCHITECTURE" = arm64 ] \
            || die "This needs 64-bit Raspberry Pi OS. This system reports '${SYSTEM_ARCHITECTURE:-nothing}'."

        # 64-bit Raspberry Pi OS reports itself as plain Debian: nothing in
        # /etc/os-release mentions a Raspberry Pi, since the 64-bit port is Debian arm64
        # with the Raspberry Pi archive on top. So check for Debian 13 or newer, which is
        # what ships the Python 3.13 this project needs, and let the board check above be
        # what says this is a Pi.
        os_pretty_name="$(read_os_release PRETTY_NAME)"
        os_id="$(read_os_release ID)"
        os_version_id="$(read_os_release VERSION_ID)"

        # ID rather than ID_LIKE. Ubuntu and 32-bit Raspbian both say ID_LIKE=debian
        # while shipping a different Python and a different package set, and neither is
        # a system this has been tested on.
        [ "$os_id" = debian ] \
            || die "This needs Raspberry Pi OS, which reports itself as Debian. This system reports '${os_pretty_name:-nothing in /etc/os-release}'."
        # Debian stable always numbers itself. Testing and unstable do not, and that is
        # the case this cannot judge rather than one it should reject outright.
        case "$os_version_id" in
            "" | *[!0-9]*)
                die "This needs Debian 13 (trixie) or newer, and '${os_pretty_name:-/etc/os-release}' gives no version to check. Use --ignore-preflight if you know it is new enough."
                ;;
        esac
        [ "$os_version_id" -ge 13 ] \
            || die "This needs Debian 13 (trixie) or newer, which is what ships Python 3.13. This system reports '$os_pretty_name'."
        info "$os_pretty_name"

        # Not a requirement, just worth saying which it is. Pi OS images carry this
        # file; plain Debian on a Pi does not, and that combination is untested rather
        # than known broken.
        if [ ! -f "$RPI_ISSUE_FILE" ]; then
            info "no $RPI_ISSUE_FILE, so this is Debian rather than Raspberry Pi OS"
        fi

        # Read the file rather than asking how big it is: files under /proc are produced
        # when they are read, and report a size of zero whatever they contain.
        #
        # /proc/asound/pcm rather than /proc/asound/cards, because cards counts
        # playback-only devices: a Pi with nothing plugged in but HDMI has two of those
        # and no microphone. Each line of pcm names its directions, so counting the ones
        # that can capture is the question actually being asked.
        #
        # grep -c prints 0 and exits 1 when nothing matches, and errors if there is no
        # ALSA at all, so both land on the same answer.
        capture_device_count="$(grep -c capture "$ASOUND_PCM_FILE" 2> /dev/null || true)"
        [ "${capture_device_count:-0}" -ge 1 ] \
            || die "No capture device found, so there is nothing to record from. Plug in a USB microphone and run this again, or pass --ignore-preflight if you are setting this up before the microphone arrives."
        info "$capture_device_count capture device(s)"
    fi
}

# The one check that has always run, since it is outside the block --ignore-preflight
# skips: the container test needs the disk as much as a Pi does.
check_free_disk() {
    available_mb="$(df -Pm / | awk 'NR == 2 { print $4 }')"
    [ "$available_mb" -ge "$REQUIRED_DISK_MB" ] \
        || die "Needs ${REQUIRED_DISK_MB} MB free on /, found ${available_mb} MB."
    info "${available_mb} MB free on /"
}

# The policy section 7 writes, one entry per unit per verb.
#
# Every unit is named in full. The obvious shorter version, `backyardchirps-*`, grants
# far more than it looks like it does: sudo matches the arguments as one concatenated
# string, so the wildcard runs across spaces and `systemctl restart backyardchirps-web
# nginx` matches the pattern too. It would also pre-approve any unit added later that
# happens to start with the prefix, which is the wrong default for a unit that runs as
# root.
render_sudoers_policy() {
    local unit verb separator=''
    printf '%s ALL=(ALL) NOPASSWD:' "$SERVICE_USER"
    for unit in "${MANAGED_UNITS[@]}"; do
        for verb in "${MANAGED_UNIT_VERBS[@]}"; do
            printf '%s \\\n  /bin/systemctl %s %s' "$separator" "$verb" "$unit"
            separator=','
        done
    done
    printf '\n'
}

# Run the machine checks and stop. For tests/unit/test_preflight.py, which points the
# four inputs above at fixtures. Deliberately before the root check and the log
# file below, so the checks can be exercised without either.
if [ "$PREFLIGHT_ONLY" = yes ]; then
    check_this_machine
    exit 0
fi

# The same idea for the policy: tests/unit/test_sudoers_policy.py reads it from here
# rather than parsing this file, so the test checks what a station is actually given.
if [ "$PRINT_SUDOERS" = yes ]; then
    render_sudoers_policy
    exit 0
fi

[ "$(id -u)" = "0" ] || die "This has to run as root. Try again with sudo."

mkdir -p "$(dirname "$LOG_FILE")"
# Everything from here on is written to the log as well as the screen, so a
# failure message can point at one file that holds the whole story.
exec > >(tee -a "$LOG_FILE") 2>&1
printf '\n===== %s =====\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# ---------------------------------------------------------------------------
# 1. Preflight
# ---------------------------------------------------------------------------
check_this_machine
check_free_disk

# ---------------------------------------------------------------------------
# 2. System packages
# ---------------------------------------------------------------------------
# No Node: the release ships the frontend already built. No git: the release is a
# tarball. No TensorFlow: BirdNET 3 runs on onnxruntime, which uv installs.
#
# python3 is named even though every Raspberry Pi OS image already has it, because
# it is what the station is built against. uv is told not to download one of its
# own, so this package is the interpreter every unit ends up starting.
say "Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
#
# gettext is msgfmt, which the deploy uses to compile the message catalogs. A release
# carries the .po files a translator edits, not the .mo files gettext reads, so without
# this the site and the setup wizard would be English whatever anybody chose.
apt-get install -y -qq --no-install-recommends \
    python3 nginx curl ca-certificates zstd libportaudio2 gettext sudo
info "python3 $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])'), nginx, curl, zstd, libportaudio2, gettext"

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

    manifest_version="$(read_manifest_field "$download_dir/manifest.json" version)"
    manifest_url="$(read_manifest_field "$download_dir/manifest.json" url)"
    manifest_sha256="$(read_manifest_field "$download_dir/manifest.json" sha256)"
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
if [ -z "$VERSION" ] || [ "$VERSION" = "$release_name" ]; then
    die "This does not look like a backyardchirps release: the tarball holds '$release_name'."
fi

RELEASE_DIR="$INSTALL_ROOT/releases/$VERSION"
LINK_DIR="$INSTALL_ROOT/current"
# What is serving right now, if anything. Only used to say something useful when the
# build fails, since the symlink is not moved until it succeeds.
PREVIOUS_RELEASE="$(readlink -f "$LINK_DIR" 2> /dev/null || true)"

say "Installing version $VERSION"
mkdir -p "$INSTALL_ROOT/releases"
# Set rather than left to the umask of whoever ran the installer. nginx and the
# service user both have to walk down to a release, and a root shell with a strict
# umask would make these 700 and stop them at the top.
chmod 755 "$INSTALL_ROOT" "$INSTALL_ROOT/releases"
# Reinstalling a version over itself is the one case with nothing to fall back to,
# because the directory being emptied here is the one that is serving. Worth saying
# out loud rather than discovering after a failed build. Deploys that install a
# build per commit never land here, since each carries its own version.
if [ -n "$PREVIOUS_RELEASE" ] && [ "$PREVIOUS_RELEASE" = "$RELEASE_DIR" ]; then
    info "this replaces the running release in place, so there is nothing to fall back to"
fi
rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"
# --no-same-owner because tar run as root otherwise restores the numeric owner
# recorded in the archive, and that is whoever built it. A tarball built on a
# developer's machine carries their uid, which on the station belongs to a different
# account or to none, so /opt would fill with files owned by a stranger. Everything
# here belongs to root and is read by the service user and nginx through its mode.
tar --zstd -xf "$tarball" -C "$RELEASE_DIR" --strip-components=1 --no-same-owner
# The mode is set here for the same reason the owner is. tar run as root restores
# the permissions recorded in the archive, and those are whatever umask the machine
# that built it had. A tarball built under umask 077 unpacks into directories nginx
# cannot enter and files it cannot read, and the only symptom is a station that
# answers 403 on every page. `a+rX` adds read to every file and traversal to every
# directory, which is what a tree holding nothing but public code should be. This
# runs before the build, so the virtualenv it creates is not touched.
chmod -R a+rX "$RELEASE_DIR"

# Everything from here builds the versioned directory. The symlink is not moved
# here: apply.sh points it at this release once the build has succeeded, right
# before it restarts anything. Until then the station carries on serving whatever
# it was already serving.
APP_DIR="$RELEASE_DIR"
info "$RELEASE_DIR"

# ---------------------------------------------------------------------------
# 4. Service user and data directory
# ---------------------------------------------------------------------------
say "Creating the service user and the data directory"
bash "$APP_DIR/deploy/provision-data-dir.sh" "$DATA_DIR" --user "$SERVICE_USER" > /dev/null
info "$SERVICE_USER owns $DATA_DIR"

# ---------------------------------------------------------------------------
# 5. Setup token, for a station that is new
# ---------------------------------------------------------------------------
# A station with no database has never run a migration, so it cannot have an admin
# and it needs a token. That is knowable here, without Django, which is why this
# runs now rather than after the build.
#
# The order matters. Everything between here and the end of the build is slow and can
# fail: a package download, a wheel that will not compile, an ssh session that drops.
# A station left with no token and no admin is one that anyone on the network can
# claim, and its wizard closes itself after the account step, because "no token" is
# also how a finished setup looks. Writing the token first means its absence has one
# meaning.
say "Checking whether the station needs a setup token"
SETUP_TOKEN=
STATION_IS_NEW=no
if [ ! -f "$DATA_DIR/detections.db" ]; then
    STATION_IS_NEW=yes
    write_setup_token
    info "$DATA_DIR/setup-token"
else
    info "this station already has a database, so the token is decided after the build"
fi

# ---------------------------------------------------------------------------
# 6. .env
# ---------------------------------------------------------------------------
# Written only once. Running the installer again on a configured station must not
# throw away its secret key and hostnames.
#
# This file holds only what has to exist before Django starts. The Telegram credentials
# are set in the wizard and stored in the database, so nothing here needs hand-editing.
say "Writing the environment file"
host_name="$(hostname)"
if [ -f "$DATA_DIR/.env" ]; then
    info "$DATA_DIR/.env already exists, leaving it alone"
else
    secret_key="$(head -c 48 /dev/urandom | base64 | tr -d '\n=+/')"
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
EOF
    chown "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR/.env"
    chmod 640 "$DATA_DIR/.env"
    info "http://$host_name.local, reachable at $allowed_hosts"
fi

# ---------------------------------------------------------------------------
# 7. sudoers
# ---------------------------------------------------------------------------
# Narrow on purpose. Root installs and the updater runs as root, so no human needs
# sudo at all.
#
# What the station does need is the web process, which runs as the service user,
# being able to restart the recorder after a settings change. That is the whole
# reason this file exists: the units in MANAGED_UNITS, the verbs in
# MANAGED_UNIT_VERBS, and nothing else. See render_sudoers_policy for why no
# pattern is used.
say "Writing the sudoers policy"
render_sudoers_policy > /etc/sudoers.d/backyardchirps
chmod 440 /etc/sudoers.d/backyardchirps
visudo -cf /etc/sudoers.d/backyardchirps > /dev/null \
    || die "The sudoers file that was just written is not valid. Remove /etc/sudoers.d/backyardchirps."
info "$SERVICE_USER may restart its own units"

# ---------------------------------------------------------------------------
# 8. Build and start
# ---------------------------------------------------------------------------
say "Building and starting the station"
info "This is the slow part: Python packages and the acoustic model."
# APP_DIR is the release being built, LINK_DIR the symlink everything points at.
# apply.sh moves the second onto the first once the build has worked, so a failure
# here leaves the station on the release it was already running.
if ! BACKYARDCHIRPS_APP_DIR="$APP_DIR" \
     BACKYARDCHIRPS_LINK_DIR="$LINK_DIR" \
     BACKYARDCHIRPS_DATA_DIR="$DATA_DIR" \
     BACKYARDCHIRPS_SERVICE_USER="$SERVICE_USER" \
         bash "$APP_DIR/deploy/apply.sh"; then
    if [ -n "$PREVIOUS_RELEASE" ] && [ -d "$PREVIOUS_RELEASE" ]; then
        printf '\nThe build failed, so nothing was switched over.\n' >&2
        printf 'Your station is still running %s.\n' "$PREVIOUS_RELEASE" >&2
    fi
    die "The build failed. See $LOG_FILE."
fi

# ---------------------------------------------------------------------------
# 9. Setup token, for a station that already had a database
# ---------------------------------------------------------------------------
# Re-running the installer is how a station updates, so most runs land here with an
# owner already in place and nothing to do. The one case worth catching is a station
# whose database exists but whose setup never finished, which is what an install
# interrupted after the migrations leaves behind.
#
# A token is never written onto a station that has an admin. That would undo its
# setup: completion is "has an admin and no longer has a token", so a fresh token
# flips a working station back to unconfigured and its owner is sent to a wizard that
# refuses to create a second account.
#
# Nothing here can fail the install. By this point the station is built, migrated and
# serving, and the only question left is whether to write one small file. Saying so
# and carrying on beats reporting a failed install that actually succeeded.
if [ "$STATION_IS_NEW" = no ] && [ -f "$DATA_DIR/setup-token" ]; then
    # A token from an earlier run that nobody has spent yet. Read it back so the
    # summary prints it again, which is the answer to having lost it.
    SETUP_TOKEN="$(cat "$DATA_DIR/setup-token")"
    say "This station still has an unused setup token"
    info "setup was never finished, so the wizard is still waiting"
elif [ "$STATION_IS_NEW" = no ]; then
    say "Checking whether the station has an owner"
    station_has_admin="$(
        sudo -u "$SERVICE_USER" env BACKYARDCHIRPS_DATA_DIR="$DATA_DIR" \
            "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" shell -c \
            'from backyardchirps.features.setup.logic import get_status
print("yes" if get_status().has_admin else "no")' | tail -n 1
    )" || station_has_admin=unknown

    case "$station_has_admin" in
        yes)
            info "it does, so no setup token is needed"
            ;;
        no)
            write_setup_token
            info "setup was never finished, so a fresh token is at $DATA_DIR/setup-token"
            ;;
        *)
            # Never guess. Guessing "no" writes a token onto what may be a working
            # station and undoes its setup; guessing "yes" is harmless but silent.
            # So do neither, and say how to write one by hand if it turns out to be
            # needed.
            info "could not tell, so nothing was written"
            info "if the wizard asks for a token you do not have, see docs/installation.md"
            ;;
    esac
fi

# ---------------------------------------------------------------------------
# 10. Old releases
# ---------------------------------------------------------------------------
# Kept so a bad version can be rolled back by pointing the symlink at the one
# before it, and pruned so a station that installs often does not fill its card.
# A station tracking main installs on every push, which is what makes this worth
# doing rather than leaving to Phase 5.
#
# Done last, after the new version is up. Pruning before the build would throw away
# the release to fall back to at exactly the moment the build failed.
#
# The live one is never a candidate, whatever its age: a re-install of the same
# version leaves it looking older than the versions it replaced.
say "Removing old releases"
current_target="$(readlink -f "$LINK_DIR")"
pruned=0
while IFS= read -r candidate; do
    [ -n "$candidate" ] || continue
    [ "$candidate" = "$current_target" ] && continue
    rm -rf "$candidate"
    pruned=$((pruned + 1))
done < <(
    find "$INSTALL_ROOT/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' 2> /dev/null \
        | sort -rn \
        | tail -n +$((KEEP_RELEASES + 1)) \
        | cut -d' ' -f2-
)
if [ "$pruned" -gt 0 ]; then
    info "removed $pruned, kept the newest $KEEP_RELEASES"
else
    info "nothing to remove"
fi

# ---------------------------------------------------------------------------
# 11. Done
# ---------------------------------------------------------------------------
# Built from the machine rather than read back out of .env, so a station whose
# hostname changed after it was installed still prints an address that works.
# ALLOWED_HOSTS carries the leading-dot form for the same reason.
site_url="http://$host_name.local"

if [ -n "$SETUP_TOKEN" ]; then
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
else
    cat <<EOF

===============================================================
 Your station is now on version $VERSION:

   $site_url

 It kept its account, settings and recordings, and it is
 recording again.

 Log:      $LOG_FILE
 Data:     $DATA_DIR
 Releases: $INSTALL_ROOT/releases
===============================================================

EOF
fi
