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

Building the tarball is `tools/build-tarball.sh`, which the workflow calls. It is a script rather
than a step inside the workflow because the container test in `tools/container/` calls it too, to
stage a tarball locally without publishing anything. An installer has to be tested against the
artifact a user actually downloads, and two copies of the code that decides what goes into that
artifact would eventually disagree.

## What gets published

Two assets on the GitHub release:

| Asset | Contents |
|---|---|
| `backyardchirps-<version>.tar.zst` | Everything needed to run: the Python package, `deploy/`, `docs/`, species seeds, and `frontend/dist` prebuilt. Everything except `deploy/deploy.sh`, which updates a git checkout and so cannot work in an unpacked release |
| `manifest.json` | Version, date, sha256, download URL, `min_upgrade_from`, changelog link |

`manifest.json` is the file an installer reads to find the latest version, and the one an
updater checks to notice a new one. `min_upgrade_from` (the `MIN_UPGRADE_FROM` env var in the
workflow) is the oldest version that can move straight to this one. It only needs raising when a
migration forces users to install an in-between release first.

Almost all of the tarball's size is the committed taxonomy, the range maps under
`species_data/locations/`, and the species photos. The code itself is a rounding error next to
them. The eBird occurrence rasters and everything under `species_data/generated/` are dropped
during staging, because a station downloads those at runtime into its data directory.

## Why the tarball is built from an allowlist

The copy step in `tools/build-tarball.sh` names the files that go in rather than listing the ones
to leave out. A release is
public and permanent, and a list of exclusions fails in a particular way: a file added to the
repo root later ships without anyone noticing. A working copy holding a real `.env` is exactly
that case, and that file has the secret key and every API token in it.

A second check then scans the staged tree for `.env`, any database, `.claude` and a few other
local files, and fails the build if it finds one. Two defences rather than one, on the step
where a mistake cannot be taken back.

## The prebuilt frontend

`tools/build-tarball.sh` builds `frontend/dist` and leaves a `.prebuilt` marker in it. `deploy/apply.sh` skips the
frontend build whenever it sees that marker, so an installed station needs no Node, no `npm ci`
and none of the minutes those take on a Pi. A git checkout has no marker and builds normally,
which is the path a deploy from source takes.

`frontend/src` is not in the tarball. What ships is the built output, and the source stays one
`git clone` away for anyone who wants it, as the AGPL requires.

## The Python version

`.python-version` ships in the tarball. Without it `uv` picks the newest interpreter it can find
on the station, which would be a different one from the version this project is developed and
tested against, and the `birdnet2` extra has no wheels for every version. Leaving it out is the
kind of mistake that only shows up on a machine nobody has set up by hand, which is what the
container test in `tools/container/` is for.

## Version reporting

`settings.VERSION` is read from the `pyproject.toml` metadata at import and shown on the server
status page. Because the project installs itself (`[build-system]` with hatchling), that metadata
is written when `uv sync` runs, so **a new version number only takes effect after a sync**. Every
deploy runs `uv sync`, so production is always correct. A development machine needs one `uv sync`
after changing the number.
