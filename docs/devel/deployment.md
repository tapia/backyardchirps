# Getting a build onto your own Pi

A station always runs from an installed release, including yours. There is no checkout on a Pi
and no deploy from source: `deploy/apply.sh` runs as root against an unpacked release and
nothing else.

That means putting your own work on a Pi is the same two moves a stranger makes, in the same
order. Build a release, then install it. The only question is who does the building and who runs
the installer.

| | Builds the tarball | Runs the installer | Triggered by |
|---|---|---|---|
| **Automatic** | a GitHub runner, on every green CI run on `main` | the self-hosted runner on your Pi | pushing to `main` |
| **Manual** | your development machine | you, over ssh | you |

Both end at the same place, so you can start with the manual path and add the runner later.

Anyone running a station rather than developing one wants
[installation.md](../installation.md) instead.

## What you end up with

```
Your network → nginx :80
                 ├─ /          Vue SPA
                 ├─ /static/   Django admin assets
                 └─ /api /admin Gunicorn (Django)

Alongside: backyardchirps-recorder  audio capture + BirdNET, always running

On disk:   /opt/backyardchirps/releases/<version>   the code, one directory per version
           /opt/backyardchirps/current              a symlink to the live one
           /var/lib/backyardchirps                  .env, database, clips, models. Never replaced
```

## Setting the Pi up

Run the installer, the same one a user runs. It handles the OS packages, the service user, the
data directory, the environment file, the sudoers policy, the units and nginx.

```bash
curl -fsSL https://raw.githubusercontent.com/tapia/backyardchirps/main/install.sh | sudo bash
```

Then open the address it prints and finish the setup wizard, which creates the admin account and
the location. Until that is done the recorder stays stopped on purpose: a station with no
coordinates would match against every species on earth.

There is nothing else to do by hand. No clone, no Node, no `.env` to write, no heredoc to paste.

## The manual path

Build a release on your development machine and install it on the Pi. `tools/build-tarball.sh`
runs on macOS and Linux, and it is the same script CI calls, so the artifact is the one a user
would download.

```bash
eval "$(bash tools/build-tarball.sh --version-suffix "+main.$(git rev-parse --short=7 HEAD)" --output-dir /tmp)"
scp "$TARBALL_PATH" pi.local:/tmp/
scp install.sh pi.local:/tmp/
ssh pi.local "sudo bash /tmp/install.sh --tarball /tmp/$TARBALL_NAME"
```

`install.sh` is copied over separately because it is not in the tarball: it is the file you have
before there is a release on the machine.

`--version-suffix` gives the build its own version, so it lands in a release directory of its own
rather than on top of the one the station is running from, and so the site can tell you which
commit is live. See [releases.md](releases.md).

Re-running the installer is how a station updates. It leaves `.env`, the database, the
recordings and the admin account alone, unpacks the new version beside the old one and swaps the
`current` symlink.

## The automatic path

`.github/workflows/deploy.yml` runs after a green CI run on `main`. A GitHub runner checks out
the exact commit CI tested, builds the tarball, and uploads it as an artifact. A second job on
the self-hosted runner downloads it, fetches `install.sh` from that same commit, and installs.

Nothing is checked out on the Pi. That is deliberate: a `workflow_run` trigger fires for pull
requests too, including from forks, and a fork's branch is called `main` by default. The
`head_repository` check in the workflow is what keeps the job to code from this repository, and
not putting a checkout step in the deploy job is the second half of the same precaution.

To register the runner:

1. **github.com → your repository → Settings → Actions → Runners → New self-hosted runner**
2. Follow the Linux arm64 instructions on the Pi.
3. Install it as a service so it survives a reboot: `sudo ./svc.sh install && sudo ./svc.sh start`

The runner account needs to be able to run the installer:

```bash
RUNNER_USER="$(whoami)"
cat <<EOF | sudo tee /etc/sudoers.d/backyardchirps-deploy > /dev/null
$RUNNER_USER ALL=(ALL) NOPASSWD: /bin/bash /home/$RUNNER_USER/backyardchirps-deploy/install.sh *
EOF
sudo chmod 440 /etc/sudoers.d/backyardchirps-deploy
sudo visudo -cf /etc/sudoers.d/backyardchirps-deploy
```

This is a broad grant, since the installer is root by nature. If you would rather not have a
GitHub-triggered job hold it, use the manual path: it costs one command and gives up nothing
else.

## What a deploy does

`install.sh` unpacks the release and hands over to `deploy/apply.sh`, which is where the work
happens:

1. Installs Python dependencies with `uv sync --no-dev`, against the system interpreter
2. Runs migrations and collects static files
3. Downloads the BirdNET 3 acoustic model and GeoModel if their upstream checksums changed
4. Installs and enables the `backyardchirps-*` units, including any new ones
5. **Points `current` at the new release**
6. Restarts the web server, and the recorder once setup is finished
7. Updates the nginx site, reloading it only if its config changed

Step 5 is where a deploy becomes real, and everything expensive happens above it. `apply.sh`
takes two directories: `BACKYARDCHIRPS_APP_DIR` is the versioned release it builds, and
`BACKYARDCHIRPS_LINK_DIR` is the symlink the units and the nginx site are written to point at.
They differ only for the length of a deploy.

So a build that fails leaves the station on the release it was already running, still able to
reboot. Pointing the symlink first would leave it running from open file handles and dying at the
next restart, which is a failure that does not show up until much later and looks like something
else when it does.

Everything can be repeated safely, which is why one script both sets up a fresh Pi and updates a
running one. Nothing serving traffic is restarted for a configuration it already has. A broken
nginx config fails the deploy while the old one carries on serving, because the reload happens
only after `nginx -t` accepts the new file.

One sharp edge remains: migrations run at step 2, above the swap, so a build that fails after
them leaves a database ahead of the code still serving. Additive migrations are harmless there,
but a destructive one would not be. The backup-before-migrating half of that belongs to the
updater, in [installer-plan.md](installer-plan.md) Phase 5.2.

To run it by hand on the station, against whatever `current` points at:

```bash
sudo bash /opt/backyardchirps/current/deploy/apply.sh
```

It reads `/etc/default/backyardchirps` to find the data directory, and refuses to run if nothing
tells it where that is.

## Moving a checkout station onto releases

Only for a Pi set up before this layout, running from `~/backyardchirps` with the units pointing
into it. It happens once and it keeps every recording, because the data directory is already
separate and never moves.

```bash
# 1. Stop the station.
sudo systemctl stop backyardchirps-web backyardchirps-recorder

# 2. Install a release over the top. It finds the existing data directory in
#    /etc/default/backyardchirps, leaves .env and the database alone, and re-renders
#    every unit to point at /opt/backyardchirps/current.
sudo bash install.sh --tarball /tmp/backyardchirps-<version>.tar.zst

# 3. Check it came up, then remove what the old layout needed.
systemctl is-active backyardchirps-web
rm -rf ~/backyardchirps
sudo rm -f /etc/sudoers.d/backyardchirps-checkout
sudo apt-get purge nodejs
```

The database is the same file throughout and no migration is reversed, so going back is
restoring the old units and pointing them at the checkout again.

## Testing the preflight checks

```bash
bash tools/test-preflight.sh
```

Seconds, no container, and it runs anywhere. `install.sh` reads the machine through five
overridable values (`DEVICE_TREE_MODEL_FILE`, `OS_RELEASE_FILE`, `ASOUND_PCM_FILE`,
`RPI_ISSUE_FILE`, `SYSTEM_ARCHITECTURE`), so the test points them at fixtures and asserts both
that a good machine is accepted and that a bad one is refused **for the right reason**.

This exists because preflight is the one part of `install.sh` the container test cannot reach: a
container is not a Pi, so `run-test.sh` passes `--ignore-preflight`. Three of the four checks
shipped broken as a result and were only found by deploying to real hardware. `--preflight-only`
runs the checks and stops, installing nothing and needing no root.

If you add a check, add a case for it here. Anything in that block is otherwise untested until it
reaches somebody's Pi.

## Testing an install without a Pi

`tools/container/run-test.sh` boots a clean Debian trixie machine under systemd, stages a release
tarball with `tools/build-tarball.sh`, runs `install.sh` inside it, checks what came out, gives
the station an owner and installs again to prove an update keeps it, then uninstalls. Nothing has
to be tagged or published, and the artifact under test is the one a user downloads. It covers
everything except real audio.

```bash
bash tools/container/run-test.sh                    # build, install, assert, tear down
bash tools/container/run-test.sh --keep             # leave it running to look around
bash tools/container/run-test.sh --runtime docker   # pin the runtime
```

The image is `debian:trixie`, matching what Raspberry Pi OS is built on. That is not a detail: a
station builds against the interpreter apt installs, so the Debian release decides which Python
the whole thing runs on.

Podman is preferred when both are installed, because it wires up cgroups for an init process on
its own where docker needs a privileged container and the cgroup filesystem mounted in.
`--runtime` overrides that.

`.github/workflows/installer.yml` runs the same script on every change to `install.sh`,
`uninstall.sh`, `deploy/`, the tarball builder or the locked dependencies. It runs on arm64,
since an installer proves little from a different architecture, and pins docker because that is
what the runner image is set up for. When it fails it prints the tail of the station's install
log into the job output, so the reason is visible without opening a container that no longer
exists.

## Where else to look

| | |
|---|---|
| [installation.md](../installation.md) | Installing a release, the path a user takes |
| [architecture.md](architecture.md) | Runtime shape, backend layout, local setup |
| [releases.md](releases.md) | Cutting a version and what ships in one |
