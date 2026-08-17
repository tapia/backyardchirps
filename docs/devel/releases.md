# Releases

## Cutting one

Versions are semver, and the tag is the trigger:

```bash
# 1. Bump `version` in pyproject.toml and commit it.
# 2. Tag and push.
git tag v0.2.0
git push origin v0.2.0
```

`.github/workflows/release.yml` does the rest. It refuses to publish when the tag and
`pyproject.toml` disagree, because the running app reports its version from `pyproject.toml`,
and a mismatch would leave the updater comparing against the wrong number. The whole backend
suite and the frontend lint both run before anything is built, so a broken tag cannot ship.

Building the tarball is `tools/build_tarball.py`, which the workflow calls. It is a script rather
than a step inside the workflow because the container test in `tools/container/` calls it too, to
stage a tarball locally without publishing anything. An installer has to be tested against the
artifact a user actually downloads, and two copies of the code that decides what goes into that
artifact would eventually disagree.

## What gets published

Two assets on the GitHub release:

| Asset | Contents |
|---|---|
| `backyardchirps-<version>.tar.zst` | Everything needed to run: the Python package, `deploy/`, `docs/`, species seeds, and `frontend/dist` prebuilt |
| `manifest.json` | Version, date, sha256, download URL, `min_upgrade_from`, changelog link |

`manifest.json` is the file an installer reads to find the latest version, and the one an
updater checks to notice a new one. `min_upgrade_from` (the `MIN_UPGRADE_FROM` env var in the
workflow) is the oldest version that can move straight to this one. It only needs raising when a
migration forces users to install an in-between release first.

Almost all of the tarball's size is the committed taxonomy and the species photos. The code
itself is a rounding error next to them. The eBird occurrence rasters and everything under
`species_data/generated/` are dropped during staging, because a station downloads those at
runtime into its data directory. Range maps are not in a release at all: they are pack content,
and a station downloads the pack for its own region rather than everybody's.

## Why the tarball is built from an allowlist

The copy step in `tools/build_tarball.py` names the files that go in rather than listing the ones
to leave out. A release is
public and permanent, and a list of exclusions fails in a particular way: a file added to the
repo root later ships without anyone noticing. A working copy holding a real `.env` is exactly
that case, and that file has the secret key and every API token in it.

A second check then scans the staged tree for `.env`, any database, `.claude` and a few other
local files, and fails the build if it finds one. Two defences rather than one, on the step
where a mistake cannot be taken back.

## The prebuilt frontend

`tools/build_tarball.py` builds `frontend/dist` and leaves a `.prebuilt` marker in it. `deploy/apply.sh` skips the
frontend build whenever it sees that marker, so an installed station needs no Node, no `npm ci`
and none of the minutes those take on a Pi. Without that marker `apply.sh` refuses to run, since
a directory with no built frontend is not a release and it has no other way to become one.

`frontend/src` is not in the tarball. What ships is the built output, and the source stays one
`git clone` away for anyone who wants it, as the AGPL requires.

## The Python version

`.python-version` does **not** ship in the tarball. A station builds against the interpreter apt
installed, because `deploy/apply.sh` sets `UV_PYTHON_DOWNLOADS=never`, and Raspberry Pi OS trixie
ships the 3.13 this project asks for. Pinning an exact version in the release would only break
every install the day Pi OS moves past it.

What a station has to agree with is `requires-python` in `pyproject.toml`, which is a range with
no upper bound. `.python-version` stays in the repository, where it pins development and CI to
one interpreter.

The failure this arrangement prevents is worth knowing, because it is silent: a downloaded
interpreter lands in the home directory of whoever ran the deploy, the service user cannot read
it, and all four units die at boot around a virtualenv built on a Python they may not open. The
container test in `tools/container/` runs on a `debian:trixie` image for this reason, so the
Debian release the station is built against is the one under test.

## Version reporting

`settings.VERSION` is read from the `pyproject.toml` metadata at import and shown on the server
status page. Because the project installs itself (`[build-system]` with hatchling), that metadata
is written when `uv sync` runs, so **a new version number only takes effect after a sync**. Every
deploy runs `uv sync`, so production is always correct. A development machine needs one `uv sync`
after changing the number.

## Builds that are not releases

A station can track `main`, which means installing a build per commit rather than per tag.
`--version-suffix` is what tells those apart:

```bash
uv run --no-project python tools/build_tarball.py --version-suffix "+main.a1b2c3d" --output-dir .
```

The suffix reaches three places: the tarball name, the directory it unpacks into, and the version
inside the staged `pyproject.toml`, which is what the status page ends up showing. Renaming the
file alone would leave a station with several builds on disk all calling themselves the same
version, and `install.sh` overwriting the release directory the running services are executing
from.

Only the staged copy is rewritten. The `pyproject.toml` in the repository is never written to.

The suffix has to be a PEP 440 local version, a `+` followed by letters, digits and dots, and the
script refuses anything else. That is also what keeps it from being a way to mistag a release: no
local version can equal the tag a release is cut from, and `release.yml` never passes the flag.

Worth knowing for the updater: `0.1.0+main.a1b2c3d` sorts **above** `0.1.0` under PEP 440. A
station tracking `main` is therefore ahead of the newest stable release by that comparison, which
is true but not what a plain "is there something newer" check should conclude.

## Region packs

The data that only makes sense for one part of the world does not ship in a release. It comes in
a **region pack**: a box, not a country, holding eBird occurrence rasters cropped to it and a
range map per species framed on it. A station resolves its coordinates against a packs index and
downloads the one covering it.

Packs and the code that builds them live in their own repository,
[tapia/backyardchirps-regional-packs](https://github.com/tapia/backyardchirps-regional-packs).
Two reasons they are not here. Drawing a range map needs contextily, geopandas and shapely, and a
station would install that stack on a Pi and never open it. And a release is tagged in semver
while a pack is dated and gets rebuilt whenever eBird publishes a new data year, so tying the two
together would force a station tag every time a pack changes.

That repository depends on this one and imports it, never the other way round. The call deciding
which species are plausible somewhere, `plausible_species_names_over`, is shared rather than
copied, so a pack cannot end up missing a raster that the station at its centre goes looking for.

## How many releases a station keeps

`install.sh` keeps the newest three directories under `releases/`, plus whatever `current` points
at whether or not it is among them. Rolling back is moving the symlink and restarting, so keeping
more than one is the point; pruning is so a station installing on every push does not fill its
card. It runs last, after the new version is up, because pruning earlier would throw away the
release to fall back to at exactly the moment the build failed.
