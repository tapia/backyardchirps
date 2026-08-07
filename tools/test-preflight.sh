#!/usr/bin/env bash
# Run install.sh's machine checks against fixtures and assert what they decide.
#
#   bash tools/test-preflight.sh
#
# Preflight is the one part of install.sh that no other test reaches. The container
# test passes --ignore-preflight, because a container has no /proc/device-tree/model
# and no sound card, and the only machine that could exercise it for real is the one
# station this project is developed against. So it shipped unverified, and the first
# time it ran on a Pi it was wrong three times over:
#
#   the OS check      looked for "raspberry" in /etc/os-release, which on 64-bit
#                     Raspberry Pi OS is Debian's own file and never says it
#   the sound check   used `test -s` on a /proc file, and those report a size of
#                     zero whatever they contain, so it refused every machine
#   the sound check   counted cards rather than capture devices, so a Pi with only
#                     HDMI attached would have passed with no microphone
#
# install.sh reads the machine through five overridable values for this reason.
# Pointing them at files in a temporary directory is what makes the checks testable
# from anywhere, which is the point: this runs on a laptop and on an x86 CI runner,
# neither of which is a Raspberry Pi.
#
# Fast and dependency-free, so it can run on pushes where the slow container test
# cannot. Written for bash 3.2, since that is what macOS ships and a developer runs
# this locally.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALLER="$REPO_ROOT/install.sh"
FIXTURES="$(mktemp -d)"
trap 'rm -rf "$FIXTURES"' EXIT

failures=0
checks=0
# What to pass the installer. Only the --ignore-preflight case changes it.
INSTALLER_FLAGS="--preflight-only"

pass() { printf '  \033[32mok\033[0m   %s\n' "$*"; }
fail() {
    printf '  \033[31mFAIL\033[0m %s\n' "$*"
    failures=$((failures + 1))
}

# Run the machine checks with every input pointed at a fixture, and check the
# verdict. `expected` is either "accept" or a fragment that has to appear in the
# refusal, so a check that starts failing for a different reason than the one under
# test cannot quietly keep passing.
#
# Output is captured rather than shown, because a refusal is the expected result for
# most of these and printing it would read as an error.
expect() {
    description="$1"
    expected="$2"
    shift 2
    checks=$((checks + 1))
    set +e
    # shellcheck disable=SC2086
    output="$(env "$@" bash "$INSTALLER" $INSTALLER_FLAGS 2>&1)"
    status=$?
    set -e

    if [ "$expected" = accept ]; then
        if [ "$status" -eq 0 ]; then
            pass "$description"
        else
            fail "$description: expected it to be accepted, got exit $status"
            printf '%s\n' "$output" | sed 's/^/       /'
        fi
        return
    fi

    if [ "$status" -eq 0 ]; then
        fail "$description: expected a refusal, but the machine was accepted"
        return
    fi
    case "$output" in
        *"$expected"*) pass "$description" ;;
        *)
            fail "$description: refused, but not for the reason expected"
            printf '       wanted to see: %s\n' "$expected"
            printf '%s\n' "$output" | sed 's/^/       /'
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
# /proc/device-tree/model is NUL-terminated on a real Pi, which is why install.sh
# strips NULs before matching it. Written the same way here.
printf 'Raspberry Pi 5 Model B Rev 1.1\0' > "$FIXTURES/model-pi5"
printf 'Raspberry Pi 4 Model B Rev 1.5\0' > "$FIXTURES/model-pi4"
printf 'Raspberry Pi 3 Model B Plus Rev 1.3\0' > "$FIXTURES/model-pi3"

# Raspberry Pi OS 64-bit carries Debian's own os-release, word for word. That is the
# fixture that matters: it is what the old check could never match.
cat > "$FIXTURES/os-trixie" <<'EOF'
PRETTY_NAME="Debian GNU/Linux 13 (trixie)"
NAME="Debian GNU/Linux"
VERSION_ID="13"
VERSION="13 (trixie)"
VERSION_CODENAME=trixie
ID=debian
EOF
cat > "$FIXTURES/os-forky" <<'EOF'
PRETTY_NAME="Debian GNU/Linux 14 (forky)"
VERSION_ID="14"
ID=debian
EOF
cat > "$FIXTURES/os-bookworm" <<'EOF'
PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"
VERSION_ID="12"
ID=debian
EOF
cat > "$FIXTURES/os-raspbian" <<'EOF'
PRETTY_NAME="Raspbian GNU/Linux 12 (bookworm)"
VERSION_ID="12"
ID=raspbian
ID_LIKE=debian
EOF
cat > "$FIXTURES/os-ubuntu" <<'EOF'
PRETTY_NAME="Ubuntu 24.04.1 LTS"
VERSION_ID="24.04"
ID=ubuntu
ID_LIKE=debian
EOF
cat > "$FIXTURES/os-sid" <<'EOF'
PRETTY_NAME="Debian GNU/Linux trixie/sid"
ID=debian
EOF

# A Pi 5 has two HDMI playback devices whether or not anything can record, which is
# why the check counts capture lines rather than cards.
cat > "$FIXTURES/pcm-with-microphone" <<'EOF'
00-00: vc4-hdmi-0 i2s-hifi-0 :  : playback 1
01-00: vc4-hdmi-1 i2s-hifi-0 :  : playback 1
02-00: USB Audio : USB Audio : capture 1
EOF
cat > "$FIXTURES/pcm-hdmi-only" <<'EOF'
00-00: vc4-hdmi-0 i2s-hifi-0 :  : playback 1
01-00: vc4-hdmi-1 i2s-hifi-0 :  : playback 1
EOF
printf 'Raspberry Pi reference 2026-08-01\n' > "$FIXTURES/rpi-issue"

# A working station. Every case below is this with one value changed, and each is
# written out in full rather than derived, so the line shows what it is testing.
MODEL_PI5="DEVICE_TREE_MODEL_FILE=$FIXTURES/model-pi5"
OS_TRIXIE="OS_RELEASE_FILE=$FIXTURES/os-trixie"
PCM_MIC="ASOUND_PCM_FILE=$FIXTURES/pcm-with-microphone"
RPI_ISSUE="RPI_ISSUE_FILE=$FIXTURES/rpi-issue"
ARCH_ARM64="SYSTEM_ARCHITECTURE=arm64"
ABSENT="$FIXTURES/absent"

printf '\n\033[1mPreflight\033[0m\n'

# ---------------------------------------------------------------------------
# Accepted
# ---------------------------------------------------------------------------
expect "a Pi 5 on trixie with a microphone" accept \
    "$MODEL_PI5" "$OS_TRIXIE" "$PCM_MIC" "$RPI_ISSUE" "$ARCH_ARM64"

expect "a Pi 4 is supported too" accept \
    "DEVICE_TREE_MODEL_FILE=$FIXTURES/model-pi4" "$OS_TRIXIE" "$PCM_MIC" "$RPI_ISSUE" "$ARCH_ARM64"

expect "a Debian newer than trixie is allowed through" accept \
    "$MODEL_PI5" "OS_RELEASE_FILE=$FIXTURES/os-forky" "$PCM_MIC" "$RPI_ISSUE" "$ARCH_ARM64"

expect "plain Debian on a Pi is allowed, with a note" accept \
    "$MODEL_PI5" "$OS_TRIXIE" "$PCM_MIC" "RPI_ISSUE_FILE=$ABSENT" "$ARCH_ARM64"

# The container test depends on this, and so does anyone setting a station up before
# the microphone arrives. Everything below is wrong on purpose.
INSTALLER_FLAGS="--preflight-only --ignore-preflight"
expect "--ignore-preflight skips every check" accept \
    "DEVICE_TREE_MODEL_FILE=$ABSENT" "OS_RELEASE_FILE=$FIXTURES/os-ubuntu" \
    "ASOUND_PCM_FILE=$ABSENT" "SYSTEM_ARCHITECTURE=amd64"
INSTALLER_FLAGS="--preflight-only"

# ---------------------------------------------------------------------------
# Refused
# ---------------------------------------------------------------------------
expect "a Pi 3 is refused by name" "Unsupported board" \
    "DEVICE_TREE_MODEL_FILE=$FIXTURES/model-pi3" "$OS_TRIXIE" "$PCM_MIC" "$RPI_ISSUE" "$ARCH_ARM64"

expect "a machine that is not a Pi is refused" "does not look like a Raspberry Pi" \
    "DEVICE_TREE_MODEL_FILE=$ABSENT" "$OS_TRIXIE" "$PCM_MIC" "$RPI_ISSUE" "$ARCH_ARM64"

expect "32-bit is refused" "needs 64-bit" \
    "$MODEL_PI5" "$OS_TRIXIE" "$PCM_MIC" "$RPI_ISSUE" "SYSTEM_ARCHITECTURE=armhf"

expect "bookworm is refused, its Python is too old" "Debian 13" \
    "$MODEL_PI5" "OS_RELEASE_FILE=$FIXTURES/os-bookworm" "$PCM_MIC" "$RPI_ISSUE" "$ARCH_ARM64"

expect "Ubuntu is refused despite ID_LIKE=debian" "reports itself as Debian" \
    "$MODEL_PI5" "OS_RELEASE_FILE=$FIXTURES/os-ubuntu" "$PCM_MIC" "$RPI_ISSUE" "$ARCH_ARM64"

expect "32-bit Raspbian is refused" "reports itself as Debian" \
    "$MODEL_PI5" "OS_RELEASE_FILE=$FIXTURES/os-raspbian" "$PCM_MIC" "$RPI_ISSUE" "$ARCH_ARM64"

expect "an unnumbered Debian says it cannot judge" "gives no version to check" \
    "$MODEL_PI5" "OS_RELEASE_FILE=$FIXTURES/os-sid" "$PCM_MIC" "$RPI_ISSUE" "$ARCH_ARM64"

expect "no os-release at all is refused" "nothing in /etc/os-release" \
    "$MODEL_PI5" "OS_RELEASE_FILE=$ABSENT" "$PCM_MIC" "$RPI_ISSUE" "$ARCH_ARM64"

expect "HDMI playback alone is not a microphone" "No capture device" \
    "$MODEL_PI5" "$OS_TRIXIE" "ASOUND_PCM_FILE=$FIXTURES/pcm-hdmi-only" "$RPI_ISSUE" "$ARCH_ARM64"

expect "no ALSA at all is refused" "No capture device" \
    "$MODEL_PI5" "$OS_TRIXIE" "ASOUND_PCM_FILE=$ABSENT" "$RPI_ISSUE" "$ARCH_ARM64"

# ---------------------------------------------------------------------------
printf '\n'
if [ "$failures" -gt 0 ]; then
    printf '\033[1;31m%d of %d checks failed.\033[0m\n\n' "$failures" "$checks"
    exit 1
fi
printf '\033[1m%d checks passed.\033[0m\n\n' "$checks"
