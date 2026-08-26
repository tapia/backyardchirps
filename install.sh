#!/usr/bin/env bash
# Install a bird recording station on a fresh Raspberry Pi.
#
#   curl -fsSL https://raw.githubusercontent.com/tapia/backyardchirps/main/install.sh | sudo bash
#
# It checks the machine, tells apt where the project's packages come from, and installs
# them. Everything after that is apt's: the files, the service user, the systemd units, the
# database migrations and the site itself all come from the packages, and updating later is
# a button on the station rather than running this again.
#
# A machine that already has a station installed from a release tarball is taken over. That
# happens inside the package rather than here, and every recording survives it.
#
# Options, mostly for testing:
#
#   --archive URL         install from a different apt repository
#   --ignore-preflight    skip the hardware checks (a container is not a Pi)
#   --preflight-only      run the hardware checks and stop, installing nothing
#   --help
#
# Everything it prints also goes to /var/log/backyardchirps-install.log.
#
# It does not configure the station and does not start recording. Both are the setup
# wizard's job: open the address this prints and it takes you there.

set -euo pipefail

# The project's own archive. A station only ever talks to this name, so moving the
# repository somewhere else is a DNS change rather than anything a station has to be told.
ARCHIVE_URL=https://apt.backyardchirps.net
PACKAGE=backyardchirps
KEYRING_PACKAGE=backyardchirps-archive-keyring
# Releases only. The per-commit suite exists for the development station, and is not
# something an owner's machine should ever follow.
SUITE=stable
ARCHITECTURE=arm64

DATA_DIR=/var/lib/backyardchirps
LOG_FILE=/var/log/backyardchirps-install.log
IGNORE_PREFLIGHT=no
PREFLIGHT_ONLY=no

# Preflight looks at the machine through these four values. They are overridable so the
# checks can be run against fixtures, which is the only way to exercise them: the
# container test is not a Raspberry Pi, and the one machine that is cannot be a test
# fixture. See tests/unit/test_preflight.py.
DEVICE_TREE_MODEL_FILE="${DEVICE_TREE_MODEL_FILE:-/proc/device-tree/model}"
OS_RELEASE_FILE="${OS_RELEASE_FILE:-/etc/os-release}"
ASOUND_PCM_FILE="${ASOUND_PCM_FILE:-/proc/asound/pcm}"
RPI_ISSUE_FILE="${RPI_ISSUE_FILE:-/etc/rpi-issue}"
SYSTEM_ARCHITECTURE="${SYSTEM_ARCHITECTURE:-$(dpkg --print-architecture 2> /dev/null || true)}"

# The virtualenv, the species data, the acoustic model and the GeoModel, with room for apt
# to hold the downloads while it works. Far less than the tarball installer needed, because
# nothing is built here any more: the packages arrive ready.
REQUIRED_DISK_MB=2048

while [ $# -gt 0 ]; do
    case "$1" in
        --archive)          ARCHIVE_URL="${2%/}"; shift 2 ;;
        --ignore-preflight) IGNORE_PREFLIGHT=yes; shift ;;
        --preflight-only)   PREFLIGHT_ONLY=yes; shift ;;
        --help)
            # The help text is the comment block between the shebang and the first blank
            # line, so there is one copy of it rather than two that can disagree.
            sed -n '2,/^$/p' "$0" | sed -e 's/^# //' -e 's/^#$//'
            exit 0
            ;;
        *) printf 'Unknown option: %s\n' "$1" >&2; exit 1 ;;
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

# Run the machine checks and stop. For tests/unit/test_preflight.py, which points the four
# inputs above at fixtures. Deliberately before the root check and the log file below, so
# the checks can be exercised without either.
if [ "$PREFLIGHT_ONLY" = yes ]; then
    check_this_machine
    exit 0
fi

[ "$(id -u)" = "0" ] || die "This has to run as root. Try again with sudo."

mkdir -p "$(dirname "$LOG_FILE")"
# Everything from here on is written to the log as well as the screen, so a failure message
# can point at one file that holds the whole story.
exec > >(tee -a "$LOG_FILE") 2>&1
printf '\n===== %s =====\n' "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"

# ---------------------------------------------------------------------------
# 1. Is this a machine a station can run on
# ---------------------------------------------------------------------------
check_this_machine
check_free_disk

# ---------------------------------------------------------------------------
# 2. What is needed to fetch one package over HTTPS
# ---------------------------------------------------------------------------
# Only these two, and only because of the chicken and egg below. Everything else a station
# needs is named in the package's own dependencies, so apt works it out.
say "Making sure this machine can fetch a package"
export DEBIAN_FRONTEND=noninteractive
apt-get update || die "apt-get update failed. Check this machine's network and its sources."
apt-get install -y curl ca-certificates > /dev/null \
    || die "Could not install curl and ca-certificates."
info "curl and ca-certificates are there"

# ---------------------------------------------------------------------------
# 3. Trust the archive
# ---------------------------------------------------------------------------
# The chicken and egg of a signed repository: apt will not fetch a package until it holds
# the key, and the key is inside a package. Downloading that one package over HTTPS and
# handing it straight to dpkg is the way in, and it is the only thing here trusted on the
# strength of TLS alone. Everything after it is signed.
#
# The version is read out of the repository rather than guessed at, because the keyring
# package is versioned by how often its own source has changed.
say "Trusting the package archive"
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

index_url="$ARCHIVE_URL/dists/$SUITE/main/binary-$ARCHITECTURE/Packages"
keyring_path="$(
    curl -fsSL "$index_url" 2> /dev/null \
        | awk -v package="$KEYRING_PACKAGE" '$1 == "Filename:" && $2 ~ package { print $2; exit }'
)" || keyring_path=""
[ -n "$keyring_path" ] \
    || die "Could not read $index_url, so there is nothing to install from. Check this machine's network."

curl -fsSL -o "$work_dir/keyring.deb" "$ARCHIVE_URL/$keyring_path" \
    || die "Could not download $ARCHIVE_URL/$keyring_path."
dpkg -i "$work_dir/keyring.deb" > /dev/null \
    || die "Could not install the archive keyring package."
info "$ARCHIVE_URL, suite $SUITE"

# ---------------------------------------------------------------------------
# 4. Install the station
# ---------------------------------------------------------------------------
# One package name. The virtualenv and the species data follow from it, and the maintainer
# scripts do everything the old installer used to do by hand: the service user, the data
# directory, .env, the setup token, the migrations, the units and the site.
say "Installing the station"
apt-get update || die "apt-get update failed after adding the archive."
apt-get install -y "$PACKAGE" || die "Installing $PACKAGE failed. The log above says why."

installed="$(dpkg-query --showformat='${Version}' --show "$PACKAGE" 2> /dev/null || true)"
info "installed $PACKAGE $installed"

# ---------------------------------------------------------------------------
# 5. Done
# ---------------------------------------------------------------------------
# The token is written by the package, and this is the only place a person is ever shown
# it. postinst cannot do this job: it runs on every upgrade as well, and it has no idea
# whether anybody is watching.
#
# The address is built from the machine rather than read back out of .env, so a station
# whose hostname changed after it was installed still prints one that works.
site_url="http://$(hostname).local"
setup_token="$(cat "$DATA_DIR/setup-token" 2> /dev/null || true)"

if [ -n "$setup_token" ]; then
    cat <<EOF

===============================================================
 Your station is installed. Open it and finish setting it up:

   $site_url

 Setup token: $setup_token

 Keep the token. The wizard asks for it, and it is the only way
 to create the first admin account.

 It is not recording yet. A station that does not know where it
 is would match every species on earth, so the recorder starts
 when you finish the wizard, not before.

 Log:  $LOG_FILE
 Data: $DATA_DIR
===============================================================

EOF
else
    cat <<EOF

===============================================================
 Your station is installed and already set up. Open it at:

   $site_url

 No setup token was written, which means this station already
 has an owner. Updates are a button on its server status page
 from now on, rather than this script.

 Log:  $LOG_FILE
 Data: $DATA_DIR
===============================================================

EOF
fi
