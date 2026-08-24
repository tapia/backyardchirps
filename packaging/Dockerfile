# The virtualenv a station runs, built at the path it will live at.
#
# Building it here rather than on the Pi is the point of the whole packaging exercise: a
# station stops compiling anything, and an update stops being the slowest and most
# failure-prone step of a release.
#
# Raspberry Pi OS 64-bit is Debian trixie underneath, so this is the same interpreter and
# the same wheels the Pi resolves. Build this image on arm64 or the venv is useless.
#
# The build path is the install path, /opt/backyardchirps/venv. That means no shebang
# rewriting afterwards and no stale .pyc files: the bytecode compiled here is bytecode the
# station uses, and it belongs to the package rather than appearing beside it later.
FROM debian:trixie AS venv

ENV DEBIAN_FRONTEND=noninteractive

# python3 is the interpreter every unit ends up starting, so it comes from apt and the
# package declares Depends: python3.13 to say so. libportaudio2 is what sounddevice binds
# to; it is here so the venv can be imported for a smoke test, and the package depends on
# it for the same reason a station needs it.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv libportaudio2 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

# The interpreter is named in full, and both halves of that matter. Downloads are off, or
# uv fetches an interpreter of its own and the venv is built against a Python no station
# has. And it is python3.13 rather than python3, because the symlinks in the venv's bin/
# point at whatever is named here: a station depends on python3.13, which is the package
# that provides /usr/bin/python3.13, while /usr/bin/python3 belongs to a metapackage that
# nothing here pulls in.
ENV UV_PYTHON=/usr/bin/python3.13 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/backyardchirps/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build
COPY pyproject.toml uv.lock ./

# --no-install-project keeps every trace of backyardchirps out of the venv. The code is
# another package, at another path, and the .pth file it drops in here is what joins the
# two. Were the project installed, its dist-info would live in this venv and the site would
# report the version of the dependency package rather than its own.
RUN uv sync --frozen --no-dev --no-install-project

# Fails the build rather than the station if a wheel resolved for the wrong platform.
RUN /opt/backyardchirps/venv/bin/python -c "import django, numpy, onnxruntime, rasterio, sounddevice"
