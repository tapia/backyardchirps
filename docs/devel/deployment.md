# Deploying from a checkout

How the project deploys itself onto a Pi from git, and what a deploy actually does. This is the
development path, used by the machine this project is developed against. Anyone running a
station installs a release instead: [installation.md](../installation.md).

The difference is what puts the code on disk. A release install unpacks a tarball; this path
pulls a git checkout. From there both hand over to the same `deploy/apply.sh`, which is the
whole build.

`birds.example.com` stands for your own hostname throughout.

## What you end up with

```
Your network → nginx :80
                 ├─ /          Vue SPA
                 ├─ /static/   Django admin assets
                 └─ /api /admin Gunicorn (Django)

Alongside: backyardchirps-recorder  audio capture + BirdNET, always running
           GitHub Actions runner  deploys on every push to main

On disk:   ~/backyardchirps          the code, replaced whole by every deploy
           /var/lib/backyardchirps   .env, database, clips, models. Never replaced
```

## Before you start

- Raspberry Pi 4 or 5, microSD card 32 GB or larger
- A USB microphone or audio interface
- A GitHub account with access to this repository

## 1. Flash the OS

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) with **Raspberry Pi OS
(64-bit)**. The 64-bit build is required, since TensorFlow has no 32-bit ARM wheels.

Click **Edit Settings** before writing and set the hostname, username, password, and WiFi
network, then enable SSH under **Services**. Write the image, boot the Pi, wait a minute, and
connect:

```bash
ssh <your-username>@raspberrypi.local
```

## 2. Give the Pi access to GitHub

Deploys pull over SSH, so the Pi needs its own key:

```bash
ssh-keygen -t ed25519 -C "raspberry-pi"
cat ~/.ssh/id_ed25519.pub
```

Paste the output into **github.com → Settings → SSH and GPG keys → New SSH key**.

## 3. Install system packages

A checkout builds the frontend on the machine, so this path needs Node, which a release install
does not: the tarball carries `frontend/dist` already built.

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git nginx curl wget libportaudio2

# Node.js 22
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# uv
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

## 4. Clone the repository

```bash
git clone git@github.com:<your-username>/backyardchirps.git ~/backyardchirps
```

The clone is all you need. Dependencies, the frontend build, migrations and static files are
part of every deploy, and they behave the same on an empty database as on an existing one.

## 5. Create the service user and choose where the data lives

The checkout is disposable: a deploy replaces it whole. Everything the station accumulates goes
somewhere else, so it survives that:

```bash
bash ~/backyardchirps/deploy/provision-data-dir.sh
export BACKYARDCHIRPS_DATA_DIR=/var/lib/backyardchirps
```

The script creates `/var/lib/backyardchirps`, records the path in the two places that need it,
and creates the `backyardchirps` system user that owns it. Pass a different directory as an
argument if you want one, and `--user NAME` for a different account.

The services run as that user rather than as you. It has no password and no login shell, and its
only extra privilege is membership of the `audio` group, which is what lets the recorder open the
microphone. Your own account keeps owning the checkout and running deploys, and drops to the
service user for anything that writes to the data directory. So a station's database and
recordings have one owner no matter who last deployed, and a web process that is somehow
compromised cannot rewrite the code it runs.

The directory itself is readable by everyone, because nginx serves the collected static files out
of it. `.env` is not: it holds the secret key and every API token, so `apply.sh` keeps it at mode
`640` on every deploy.

Those two places are read by different things. A deploy triggered by GitHub Actions carries none
of your shell environment, so it reads `/etc/default/backyardchirps`. Anything you run by hand,
`manage.py` included, reads the exported variable, which the script adds to `~/.bashrc`. The
`export` above is only for the shell you are in now.

Getting one without the other is the trap worth knowing about: every deploy you run by hand
keeps working, while the first one CI runs builds an empty database in the checkout and points
the station at it. `apply.sh` refuses to deploy while the two disagree, and prints the command
that fixes it, so you find out at the next deploy rather than months later.

Skip this step entirely and everything lands in the checkout. That is fine on a machine you are
only experimenting with, but it means a deploy takes the database and the recordings with it.

## 6. Create `.env`

It goes in the data directory, not the checkout:

```bash
cp ~/backyardchirps/.env.example /var/lib/backyardchirps/.env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Fill in at least:

| Variable | Value |
|---|---|
| `SECRET_KEY` | the string generated above |
| `ALLOWED_HOSTS` | `birds.example.com,localhost,127.0.0.1` |
| `CSRF_TRUSTED_ORIGINS` | `https://birds.example.com` |

That is the whole file. The credentials for Telegram, xeno-canto and ipgeolocation.io are
settings rather than environment variables, so they are set in the web UI and stored in the
database.

## 7. Let `deploy.sh` configure the machine

The script installs the systemd units and the nginx site itself, so it needs passwordless
`sudo` for exactly the commands that touch the system:

```bash
APP_USER="$(whoami)"
cat <<EOF | sudo tee /etc/sudoers.d/backyardchirps > /dev/null
$APP_USER ALL=(backyardchirps) NOPASSWD: ALL
$APP_USER ALL=(ALL) NOPASSWD: \\
  /usr/bin/tee /etc/systemd/system/backyardchirps-*, \\
  /usr/bin/tee /etc/nginx/sites-available/backyardchirps, \\
  /bin/ln -sf /etc/nginx/sites-available/backyardchirps /etc/nginx/sites-enabled/backyardchirps, \\
  /bin/rm -f /etc/nginx/sites-enabled/default, \\
  /usr/sbin/nginx -t, \\
  /bin/systemctl daemon-reload, \\
  /bin/systemctl enable *, \\
  /bin/systemctl enable --now *, \\
  /bin/systemctl start *, \\
  /bin/systemctl restart *, \\
  /bin/systemctl reload *
EOF
sudo chmod 440 /etc/sudoers.d/backyardchirps
```

This is a wider policy than a release install gets. There, root installs and the updater runs as
root, so no human needs `sudo` at all and the only grant is the service user restarting its own
units.

The first line is a different kind of grant from the rest. It does not allow any new command as
root: it allows running commands **as the `backyardchirps` service user**, which owns the data
directory. The deploy needs it for every step that touches that directory, starting with reading
`.env`, so a deploy fails immediately without it. See step 5 for why the two accounts are
separate.

The `systemctl` wildcards are deliberate. On a machine that does nothing else, being able to
restart any unit is already close to being root, so naming every unit and verb would gain very
little and would need editing each time a unit is added. The file writes are pinned to exact
paths, because that is where a typo would really do damage.

A unit added later needs no change here, as long as it is named `backyardchirps-*` and appears in
`DAEMONS` or `TIMED_JOBS` in `deploy/apply.sh`.

## 8. Register the GitHub Actions runner

1. **github.com → your fork → Settings → Actions → Runners → New self-hosted runner**
2. Select **Linux / ARM64**
3. Run the download and configuration commands shown there, accepting all defaults

Then install it as a service:

```bash
cd ~/src/actions-runner
sudo ./svc.sh install "$(whoami)"
sudo ./svc.sh start
```

## 9. Deploy

```bash
bash ~/backyardchirps/deploy/deploy.sh
```

On a machine that has never been deployed to, this installs dependencies, builds the frontend,
creates the database, downloads the BirdNET 3 model, and starts every service. Check it worked:

```bash
sudo systemctl status nginx backyardchirps-web backyardchirps-recorder \
    backyardchirps-update-species.timer backyardchirps-clip-disk-quota.timer
```

Then open the Pi's address on your network, `http://raspberrypi.local` unless you changed the
hostname when flashing.

## 10. Create the admin account

Settings, detection rules, and the review queue need a staff account, and a fresh database has
none. **The recorder is stopped until one exists**: `apply.sh` refuses to start a station that
has not been configured, because with no coordinates BirdNET matches against every species on
earth.

The site takes you to the setup wizard on its own. A checkout has no setup token, so it asks
for none, and finishing it creates the account and starts the recorder. That is the path worth
taking, if only because it is the one your users take.

To do it by hand instead:

```bash
cd ~/backyardchirps
echo "$BACKYARDCHIRPS_DATA_DIR"     # must print your data directory, not empty
DJANGO_SUPERUSER_PASSWORD='<pick-a-password>' \
    uv run python manage.py createsuperuser --noinput --username admin --email ''
sudo systemctl start backyardchirps-recorder
```

Check that variable first. Empty means this shell predates step 5, and the account would be
created in a database the station never reads. Open a new session, or export it by hand.

The empty `--email` is deliberate: the field is optional, but `--noinput` still insists on being
given a value. Running the command a second time fails saying the username is taken, which is
all the confirmation you need that the account exists.

The explicit `systemctl start` is what the wizard would have done for you. Without it the
recorder waits for the next deploy, which will start it now that the station has an owner.

## Deploys after that

Every push to `main` triggers one. The runner on the Pi picks up the commit and runs
`deploy.sh`, which pulls the code and hands over to `apply.sh`. That second script is where the
work happens:

1. Updates Python dependencies and rebuilds the frontend
2. Runs migrations and collects static files
3. Downloads the BirdNET 3 acoustic model and GeoModel if their upstream checksums changed
4. Installs and enables the `backyardchirps-*` units, including any new ones
5. Restarts the web server and recorder
6. Updates the nginx site, reloading it only if its config changed

Every step can be repeated safely, which is why one script both sets up a fresh Pi and updates a
running one. Nothing serving traffic is restarted for a configuration it already has. A broken
nginx config fails the deploy while the old one carries on serving, because the reload happens
only after `nginx -t` accepts the new file.

To deploy by hand at any time:

```bash
bash ~/backyardchirps/deploy/deploy.sh
```

## Migrating an older station to the service user

Only for a station set up before the `backyardchirps` account existed, where everything is owned
by the deploying user and the units run as that user too. It happens once, it keeps every
recording, and it is reversible.

Check whether it applies:

```bash
id backyardchirps                                          # no such user
systemctl show backyardchirps-web -p User --value          # your own name
```

If the account is missing **and** the data lives outside the checkout, `apply.sh` now refuses to
deploy, because continuing would leave the database owned by whoever ran it while the units
expect to run as somebody else.

```bash
# 1. Stop the station. The database must not be written while it changes hands.
sudo systemctl stop backyardchirps-web backyardchirps-recorder
sudo systemctl stop backyardchirps-update-species.timer backyardchirps-clip-disk-quota.timer

# 2. Create the account. Safe on a machine that already has the data directory:
#    it leaves the directory, the default file and the profile line as they are.
bash ~/backyardchirps/deploy/provision-data-dir.sh

# 3. Hand the data over. The script above chowns the directory itself but not what
#    is inside it, which is the whole of this step.
sudo chown -R backyardchirps:backyardchirps /var/lib/backyardchirps

# 4. Update the sudoers policy: re-run the heredoc from step 7 above. The file on
#    an older station is missing its first line, the one that lets you act as the
#    service user, and the deploy fails on the first thing it reads without it.

# 5. Deploy. This re-renders the units with the new User= and starts everything.
bash ~/backyardchirps/deploy/deploy.sh
```

Then check it took:

```bash
systemctl show backyardchirps-web -p User --value          # backyardchirps
sudo -u backyardchirps test -r /var/lib/backyardchirps/.env && echo "reads .env"
systemctl is-active backyardchirps-web backyardchirps-recorder
```

The site should answer, and a new detection should appear within a few minutes. That last one is
the real test: it proves the recorder can both open the microphone through the `audio` group and
write to a database it did not own an hour ago.

**What changes for you afterwards.** The database and `.env` stop being yours. A `manage.py`
command run by hand can still read most things but can no longer write, so it needs the service
user:

```bash
sudo -u backyardchirps env BACKYARDCHIRPS_DATA_DIR=/var/lib/backyardchirps \
    ~/backyardchirps/.venv/bin/python ~/backyardchirps/manage.py <command>
```

**Going back**, if something is wrong: `sudo chown -R <your-username>: /var/lib/backyardchirps`,
`sudo userdel backyardchirps`, then deploy again. No migration runs and no schema changes, so the
database is the same file either way.

## Testing an install without a Pi

`tools/container/run-test.sh` boots a clean Debian machine under systemd, stages a release
tarball with `tools/build-tarball.sh`, runs `install.sh` inside it, checks what came out, and
uninstalls. Nothing has to be tagged or published, and the artifact under test is the one a user
downloads. It covers everything except real audio.

```bash
bash tools/container/run-test.sh                    # build, install, assert, tear down
bash tools/container/run-test.sh --keep             # leave it running to look around
bash tools/container/run-test.sh --runtime docker   # pin the runtime
```

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
