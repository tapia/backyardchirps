# Installation

From a blank SD card to a live site. Allow about an hour, most of it spent waiting for
downloads.

`deploy/deploy.sh` does everything it possibly can. The manual steps below are the ones that
genuinely cannot be automated: logging in to things by hand, and giving the script permission
to configure the machine.

`birds.example.com` stands for your own hostname throughout. The station serves plain HTTP on
your own network. Putting it on the public internet is not covered here.

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

## 5. Choose where the data lives

The checkout is disposable: a deploy replaces it whole. Everything the station accumulates goes
somewhere else, so it survives that:

```bash
bash ~/backyardchirps/deploy/provision-data-dir.sh
export BACKYARDCHIRPS_DATA_DIR=/var/lib/backyardchirps
```

The script creates `/var/lib/backyardchirps`, gives it to your user, and records the path in the
two places that need it. Pass a different directory as an argument if you want one.

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
| `SITE_URL` | `https://birds.example.com` |
| `TELEGRAM_TOKEN` | optional, for notifications |
| `TELEGRAM_CHAT_ID` | optional, for notifications |
| `XENO_CANTO_API_KEY` | optional, for reference calls on species pages |

## 7. Let `deploy.sh` configure the machine

The script installs the systemd units and the nginx site itself, so it needs passwordless
`sudo` for exactly the commands that touch the system:

```bash
APP_USER="$(whoami)"
cat <<EOF | sudo tee /etc/sudoers.d/backyardchirps > /dev/null
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
none:

```bash
cd ~/backyardchirps
echo "$BACKYARDCHIRPS_DATA_DIR"     # must print your data directory, not empty
DJANGO_SUPERUSER_PASSWORD='<pick-a-password>' \
    uv run python manage.py createsuperuser --noinput --username admin --email ''
```

Check that variable first. Empty means this shell predates step 5, and the account would be
created in a database the station never reads. Open a new session, or export it by hand.

The empty `--email` is deliberate: the field is optional, but `--noinput` still insists on being
given a value. Running the command a second time fails saying the username is taken, which is
all the confirmation you need that the account exists.

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
