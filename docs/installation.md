# Installation

From a blank SD card to a live site. Flash the card, run one command, and wait for the
downloads.

## What you need

- Raspberry Pi 4 or 5, microSD card 32 GB or larger
- A USB microphone or audio interface
- Raspberry Pi OS, 64-bit

Nothing else is supported. The installer checks the board, the architecture and the operating
system before it writes anything, and stops with a clear message when one of them is wrong.

## 1. Flash the OS

Use [Raspberry Pi Imager](https://www.raspberrypi.com/software/) with **Raspberry Pi OS
(64-bit)**.

Click **Edit Settings** before writing and set the hostname, username, password, and WiFi
network, then enable SSH under **Services**. Write the image, boot the Pi, plug in the
microphone, wait a minute, and connect:

```bash
ssh <your-username>@raspberrypi.local
```

## 2. Run the installer

```bash
curl -fsSL https://raw.githubusercontent.com/tapia/backyardchirps/main/install.sh | sudo bash
```

It downloads the latest release, installs the system packages it needs, creates the service
user and the data directory, builds the Python environment, downloads the BirdNET acoustic
model, and starts everything. The Python environment and the model are what take the time.

When it finishes it prints the address of your station and a setup token:

```
 Your station is running.

   http://raspberrypi.local

 Setup token: 4f3a...
```

Keep the token. The setup wizard needs it, and it is the only way to create the first admin
account.

Open that address from any machine on the same network and the site is there.

**This version has no wizard yet.** The station records and identifies from the moment it
starts, but nothing can tell it where it is, and without coordinates it matches every call
against every species on earth. It works, and it guesses badly. The next version adds the
wizard, and updating to it is one command.

## What it installed

```
/opt/backyardchirps/
├── releases/<version>/   the code, one directory per installed version
└── current -> releases/<version>

/var/lib/backyardchirps/
├── .env  detections.db  setup-token
├── clips/     the recordings
├── models/    BirdNET acoustic model and GeoModel
└── species/   taxonomy and per-station species data
```

Code and data are kept apart on purpose. An update replaces the first and never touches the
second, so your recordings survive every version.

Four systemd units run as a dedicated `backyardchirps` user, which has no password and no login
shell:

| Unit | Does |
|---|---|
| `backyardchirps-web` | The website and the API |
| `backyardchirps-recorder` | Audio capture and identification, always running |
| `backyardchirps-update-species.timer` | Rebuilds the station's species list |
| `backyardchirps-clip-disk-quota.timer` | Deletes old recordings when the disk fills |

Check them at any time:

```bash
sudo systemctl status backyardchirps-web backyardchirps-recorder
```

## Reaching the station by name

The installer sets the site up for `http://<hostname>.local` plus the address the Pi had when it
ran. The `.local` name keeps working if the address changes, but only from machines that speak
mDNS.

The raw address is the fragile part: your router can hand the Pi a different one after a reboot,
and the site then refuses the request. Set a DHCP reservation for the Pi in your router, which
fixes it permanently.

The station serves plain HTTP on your own network. Putting it on the public internet is not
covered here, and is not something the project supports today.

## Updating

Re-run the installer. It fetches the newest release, unpacks it beside the current one, swaps
the `current` symlink, runs migrations and restarts the services. Your `.env`, database and
recordings are left alone.

## Uninstalling

```bash
curl -fsSL https://raw.githubusercontent.com/tapia/backyardchirps/main/uninstall.sh | sudo bash
```

That stops and removes the software and keeps every recording, so reinstalling later picks up
where you left off. Add `--all` to delete the data as well, which asks for confirmation and
cannot be undone. Either way nginx, uv and the other system packages stay: they were useful
before this and something else may be using them.

## When something goes wrong

Everything the installer printed is also in `/var/log/backyardchirps-install.log`, including the
output of the step that failed.

| Symptom | Look at |
|---|---|
| The installer stopped early | The last lines of the log. Every failure names what it wanted |
| The site does not answer | `sudo systemctl status backyardchirps-web nginx` |
| No detections appear | `sudo journalctl -u backyardchirps-recorder -n 50`, usually the microphone |
| The browser says the host is not allowed | The address changed. See "Reaching the station by name" |

The [admin guide](admin-guide.md) covers running the station day to day.

## Installing from a git checkout

The path above is for running a station. If you are working on the code, deploying from a
checkout is a different procedure: see [deployment.md](devel/deployment.md).
