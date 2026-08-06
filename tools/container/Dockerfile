# A throwaway station to test deploys against.
#
# Raspberry Pi OS 64-bit is Debian bookworm underneath, and on an arm64 host this
# runs natively, so Python wheels resolve the way they will on the Pi. That is the
# point of the exercise: an installer cannot be tested on a machine that already
# works, and it cannot be trusted on a machine of a different architecture.
#
# What it covers: paths, permissions, systemd units, the nginx site, migrations
# against an empty database, and the data-directory guard.
#
# What it cannot: real audio, real Pi hardware. /proc/device-tree/model does not
# exist here, so anything that preflights on it needs a way to be told otherwise.
FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive
ENV container=docker

# Deliberately minimal: systemd so units can be tested, and sqlite3 so the test can
# look inside the database afterwards. Everything the station itself needs, uv
# included, is install.sh's job, so leaving it out here is what proves the
# installer installs it.
RUN apt-get update && apt-get install -y --no-install-recommends \
        systemd systemd-sysv dbus \
        ca-certificates sudo procps sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# systemd in a container: units that want real hardware never become ready, and
# would hold up boot forever.
RUN find /lib/systemd/system/sysinit.target.wants/ -name 'systemd-tmpfiles-setup*' -delete \
    && rm -f /lib/systemd/system/multi-user.target.wants/* \
             /etc/systemd/system/*.wants/* \
             /lib/systemd/system/local-fs.target.wants/* \
             /lib/systemd/system/sockets.target.wants/*udev* \
             /lib/systemd/system/sockets.target.wants/*initctl* \
             /lib/systemd/system/basic.target.wants/* \
    && rm -f /lib/systemd/system/getty.target.wants/*

STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
