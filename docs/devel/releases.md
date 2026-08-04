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

Almost all of the tarball's size is the committed taxonomy and the per-location seeds. The code
itself is a rounding error next to them.

## Why the tarball is built from an allowlist

The copy step names the files that go in rather than listing the ones to leave out. A release is
public and permanent, and a list of exclusions fails in a particular way: a file added to the
repo root later ships without anyone noticing. A working copy holding a real `.env` is exactly
that case, and that file has the secret key and every API token in it.

A second check then scans the staged tree for `.env`, any database, `.claude` and a few other
local files, and fails the build if it finds one. Two defences rather than one, on the step
where a mistake cannot be taken back.

## The prebuilt frontend

CI builds `frontend/dist` and leaves a `.prebuilt` marker in it. `deploy/apply.sh` skips the
frontend build whenever it sees that marker, so an installed station needs no Node, no `npm ci`
and none of the minutes those take on a Pi. A git checkout has no marker and builds normally,
which is the path a deploy from source takes.

`frontend/src` is not in the tarball. What ships is the built output, and the source stays one
`git clone` away for anyone who wants it, as the AGPL requires.

## Version reporting

`settings.VERSION` is read from the `pyproject.toml` metadata at import and shown on the server
status page. Because the project installs itself (`[build-system]` with hatchling), that metadata
is written when `uv sync` runs, so **a new version number only takes effect after a sync**. Every
deploy runs `uv sync`, so production is always correct. A development machine needs one `uv sync`
after changing the number.
