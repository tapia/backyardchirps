# A throwaway station to test deploys against.
#
# Raspberry Pi OS 64-bit is Debian trixie underneath, and on an arm64 host this
# runs natively, so Python wheels resolve the way they will on the Pi. That is the
# point of the exercise: an installer cannot be tested on a machine that already
# works, and it cannot be trusted on a machine of a different architecture.
#
# The Debian release matters as much as the architecture now. A station builds
# against the interpreter apt installs, so trixie is what decides whether the
# version this project asks for is the version it gets.
#
# What it covers: paths, permissions, systemd units, the nginx site, migrations
# against an empty database, and the data-directory guard.
#
# What it cannot: real audio, real Pi hardware. /proc/device-tree/model does not
# exist here, so anything that preflights on it needs a way to be told otherwise.
FROM debian:trixie

ENV DEBIAN_FRONTEND=noninteractive
ENV container=docker

# Deliberately minimal: systemd so units can be tested, and sqlite3 so the test can
# look inside the database afterwards. Everything the station itself needs arrives in
# a package, so leaving it out here is what proves the packages carry it.
#
# The last two are test fixtures rather than anything a station has. apt-utils is
# apt-ftparchive, which indexes the local package repository these tests install from.
# zstd unpacks a release tarball, which happens in one place only: building an old
# station for the takeover to take over. Both leave when the tarball path does.
RUN apt-get update && apt-get install -y --no-install-recommends \
        systemd systemd-sysv dbus \
        ca-certificates sudo procps sqlite3 apt-utils zstd \
    && rm -rf /var/lib/apt/lists/*

# The debian image ships a policy-rc.d that answers "no" to every request to start a
# service, so that building an image never brings one up. This machine is standing in for
# a Pi, and a package's maintainer scripts ask that policy before starting anything, so
# leaving it here would mean testing an install that starts nothing.
RUN rm -f /usr/sbin/policy-rc.d

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
