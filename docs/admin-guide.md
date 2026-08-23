# Admin guide

Running the station day to day. For setting up a new Pi, see
[installation.md](installation.md).

Log in at `/login` with a staff account. **Settings**,
**Customized species**, and **Server status** then appear under **Admin** in the navbar;
without staff access they redirect to the login page.

The account is the one you made in the setup wizard when you installed the station.

## Settings

Four tabs, following the path a sound takes through the station: where it is heard, what hears
it, what identifies it, and who gets told.

| Tab | Holds |
|---|---|
| Station | Where the microphone is, the region pack for that part of the world, the units the weather is shown in |
| Recording | Which input to listen to, and how much disk the clips may fill |
| Detection | The acoustic model, the three confidence thresholds, and the rules for a single species |
| Notifications | The Telegram credentials and the rules that decide what is worth a message |

Each tab has one save button at the bottom, and it stays in view as you scroll, so on a long tab
you never have to go looking for it. It becomes active once something on the tab has changed,
and it saves that tab alone: a half-typed value on another tab cannot travel with it. The tab is
part of the address, so `/settings/detection` opens straight on that one.

### Station

#### Recording station coordinates

Latitude and longitude of the microphone. BirdNET uses these to rule out species that do not
occur in the area, so a wrong value here damages every identification, with no visible sign
that anything is wrong.

Click the map to set both at once, the same picker the setup wizard shows. Typing in the two
fields moves the pin, and the button in the corner of the map makes it fill the window, which is
the easiest way to point at a roof rather than a village. Escape puts it back. The map needs an
internet connection; without one it stays empty and the two fields still work.

#### Region pack

A region pack holds the range maps, the seasonality charts and the reference recordings for one
box on the map. A station downloads the pack covering its own coordinates, so nobody pays for
data about the other side of the world. Without one the site works normally and a species page
shows none of the three.

The setup wizard installs a pack when the station is first configured, so most stations never
need this card. It is here for moving the station, and for a pack that did not install the first
time.

The card shows the pack in use and looks up what covers the coordinates above it. Change those
coordinates and it offers the pack for the new point rather than switching on its own, since a
station near the edge of its box would otherwise re-download everything because somebody nudged
the pin by a few metres.

**Packs are rebuilt from time to time**, to fix data or to carry something new. When the pack
you have was built on a different date from the one published, the card says so and offers to
update it. Nothing is downloaded until you press the button, and the pack in use keeps working
the whole time: it is only replaced once the new one has arrived complete and been checked.

**Downloading takes minutes.** How many depends on how many species live in the box, since a pack
carries one cropped raster per species. The download runs on the station rather than in the
browser, so closing the tab or letting a phone lock its screen does not stop it: come back to the
page and the bar is still moving. If it fails the card says so and the button offers another try.
The reason is in the journal:

```bash
journalctl -u backyardchirps-web -n 50 --no-pager
```

**Switching packs is safe.** Nothing in the database is keyed to a pack: detections reference
species, and a pack only supplies pictures and probabilities. A switch changes what a species page
can draw and nothing about your history. Restart the web service afterwards, though, so that both
of its workers read the new pack rather than the one they already had open:

```bash
sudo systemctl restart backyardchirps-web
```

**When no pack covers you**, the card names the nearest one, says how far away it is, and links to
a form asking for a new one. Give it your coordinates above everything else: several requests near
each other are one pack, and a request nobody makes is a pack that never gets built. You can
install the nearest pack anyway, but expect little from it. Its range maps are framed on that
region, and no species gets a seasonality chart at all, because the occurrence data is cropped to
a box your station is not in.

**Old packs stay on disk**, so going back to one is not a second download. Each is a directory:

```bash
ls /var/lib/backyardchirps/region-packs/
sudo rm -rf /var/lib/backyardchirps/region-packs/<id>    # one you are finished with
```

A station that has been recording since before packs existed has one more thing to clear. Its old
worldwide rasters are moved aside on the first install instead of being deleted, since they are
not the installer's to throw away, and they are large. Nothing reads them:

```bash
sudo rm -rf /var/lib/backyardchirps/species/ebird_occurrence.superseded
```

#### Weather units

The units the weather widget uses: Celsius or Fahrenheit, km/h or mph. They change what is
drawn, nothing about what is recorded. The forecast itself comes from the station's coordinates
above.

### Recording

#### Microphone

Which input the recorder listens to. **System default** is right when the Pi has one sound
card, which is the usual case; pick a device by name when it has more than one, or when a USB
microphone is not the one being used.

Saving restarts the recorder, since it opens the microphone once at startup and never looks
again.

If the list is empty the operating system sees no recording device at all. Check the cable and
`arecord -l` before looking anywhere else.

#### Storage

Recordings pile up forever unless you set a limit. **Maximum disk usage** is a percentage of
the disk holding the clips folder, 85% by default. Whenever usage goes above it, a scheduled
job deletes the audio of the oldest clips.

Only the audio goes. The detection records stay, so history, charts and species counts are
unaffected. The old entries simply lose their play button.

### Detection

#### Acoustic model

**BirdNET 3** (the default) or **BirdNET 2**. BirdNET 3 is still a preview release and is
generally more accurate. If it starts behaving oddly, switch back.

BirdNET 2 is not installed by default, because it needs TensorFlow and most stations never run
it. Switching to it therefore takes one extra command before the restart:

```bash
cd ~/backyardchirps && uv sync --no-dev --extra birdnet2
sudo systemctl restart backyardchirps-recorder
```

Forget it and the recorder refuses to start, saying exactly this. Later deploys keep it
installed on their own, for as long as BirdNET 2 stays selected.

Both models score on similar scales, so the thresholds below go on working after a switch.
Older detections keep the confidence given to them by whichever model made them.

#### BirdNET analysis

Three thresholds, and only two of them change what gets recorded.

| Setting | Default | Effect |
|---|---|---|
| Low confidence | 40% | BirdNET's floor. Anything below is discarded and never reaches the database. |
| Medium confidence | 70% | The auto-confirm bar. At or above it a detection is published directly; below it, it waits for review. |
| High confidence | 90% | Display only. Sets what the navbar's "High" filter shows. |

Raising **Low** means fewer detections overall and a quieter site. Raising **Medium** means the
same detections, with more of them queued. If the review queue has more in it than you can get
through, lower Medium. If rubbish is reaching the public pages, raise it.

#### Per-species rules

A species can be blacklisted, or given its own auto-confirm threshold in place of the medium
one above. The card counts the species that have rules of their own and opens the page that
lists them. See [Per-species detection rules](#per-species-detection-rules) below for what the
two rules do.

### Notifications

#### Telegram

The bot token and the chat ID. Without them nothing is sent and everything else on the site
works as usual. Get a token from @BotFather.

Both are stored in the database, so they survive an update and never need `.env` to be edited.
They are the only credentials a station asks for: sunrise and sunset are worked out from the
station's own coordinates, and the reference recordings on a species page come from the region
pack.

#### Notification rules

Telegram messages, once you have filled in the bot token and chat ID above. Each rule has its
own switch and its own minimum confidence, so you can be strict about what is worth being
interrupted for.

| Rule | Default confidence | Fires when |
|---|---|---|
| New species | 90% | A species is detected for the very first time |
| First today | 90% | First detection of a species today |
| First this year | 90% | First detection of a species this calendar year |
| Rare species | 75% | A species that rarely turns up here is heard |
| Long absent | 90% | A species returns after 30+ days (configurable) |
| Pending validation | n/a | Something landed in the review queue |

Messages go out in Spanish by default; change it under **Send messages in**.

### What needs a recorder restart

Settings live in the database and take effect at once, with four exceptions. The recorder opens
the microphone and builds its analyzer only when it starts, so the coordinates, the acoustic
model, the low confidence threshold and the microphone are read once and then kept. The
microphone looks after itself, restarting the recorder when you save it. For the other three:

```bash
sudo systemctl restart backyardchirps-recorder
```

Everything on this page not in that list takes effect on the next page load.

## Per-species detection rules

Some species get reported far more often than they actually occur. Two overrides deal with
that, reachable from **Settings → Detection**, from a species' own page, or inside
the review dialog. Both work only on species heard here at least once. Anyone can see the rules
in place, but only admins can change them.

**A custom auto-confirm threshold** replaces the global 70% bar for one species. A bird that
keeps arriving in the queue and is almost never wrong can be given a lower bar.

Lowering the bar also reaches backwards: detections already waiting that now clear it are
confirmed at once, keeping their original confidence. That is not the same as a person
confirming them, so they are not set to 100%. Raising or removing the bar changes future
detections only, and nothing already confirmed goes back to the queue.

**Blacklisting** is for a species that should not be here at all. New results are dropped
straight after analysis: no record, no recording, no notification. Existing detections are not
deleted, but they are hidden everywhere (catalogue, feeds, charts, review queue, its own page),
so the site shows the species as never detected and marks it blacklisted. It can still be found
through search.

Two things worth knowing:

- **Other species in the same clip are unaffected.** BirdNET reports everything it hears above
  the floor, not only the best match. Blacklisting a species that produces constant false
  matches therefore often lets the real bird behind it come through, the one that kept being
  ranked second.
- **It is fully reversible.** Taking a species off the blacklist brings its whole history back
  exactly as it was. The only real gap is the blacklisted period itself, when nothing was
  recorded.

## Monitoring

**Server status** (`/server-status`) shows CPU temperature, load, memory, disk, and the sound
processing queue. It turns red past 75°C, 90% load, 85% memory, or the storage limit you
configured.

The version your station runs sits next to the heading. A station checks once a day whether a
newer release has been published, and when there is one a badge appears beside that version,
linking to what changed. Nothing is installed for you: updating is still re-running the
installer, as [installation.md](installation.md) describes.

Two other things that badge can say. "Not checked yet" means the daily check has not run since
the station was installed, which sorts itself out overnight. "Could not check for updates" means
it ran and failed, usually because the station has no route to the internet, and it stays until
a later check succeeds. Neither means you are up to date.

**Installing an update** is the button beside that badge. The station backs up its database
first, into `backups/` in the data directory, then installs the new release beside the old one
and switches to it. Your settings, recordings and account are untouched: only the code is
replaced. It takes a few minutes and the site goes down briefly partway through, so a failed
page load while it runs is expected. The page follows along and tells you when it is finished.

An update that says it cannot be installed over your version is telling you the release is too
far ahead of the installer you have, so update by hand as
[installation.md](installation.md) describes.

**Going back to the previous release** is the other button, and it appears once an update has
finished. Read this before using it.

Most of the time going back is cheap: the station reinstalls the release it was on before and
your data is untouched. It stops being cheap when the update changed the shape of the database.
The old code cannot read the new shape, so going back also restores the copy taken just before
the update, and **every detection recorded since that update is dropped**. There is no way to
keep both: the recordings are still on disk, but the station no longer has rows for them.

The station does not throw the newer database away. It is moved aside into `backups/` in the data
directory, named `detections-rolled-back-<timestamp>.db`, so somebody who knows SQLite can get
the lost detections out of it afterwards.

If the update did not change the database, nothing is restored and nothing is lost. The station
works out which case it is on its own, by asking the older release which migrations it knows
about. You are not expected to.

One more thing it does without being asked: if an update installs but the site does not answer
afterwards, the station goes back on its own rather than leaving you with a machine you can only
reach over ssh.

The **sound processing queue** card answers one question: is the recorder analyzing clips
faster than they arrive? A clip arrives every 1.5 seconds, so there are 1500 ms available to
analyze each one. The big number is the average analysis time as a percentage of that, and it
turns red at 80%. Below 100% the queue always empties again. At 100% it stops emptying and the
backlog grows without limit. The line underneath (`3 queued (peak 12) · 1420 / 1500 ms per
clip`) keeps a short delay visible after it has passed. When the recorder is not running, the
card reads "Recorder offline".

A load that stays above 80% means the Pi cannot keep up, and detections will fall further and
further behind real time.

**All detections** (`/detections`, in the gear menu) lists every detection newest first with
its per-clip analysis time. Same signal as the queue card, one detection at a time.

## When something looks wrong

The site is up but nothing new appears:

```bash
sudo systemctl status backyardchirps-recorder
journalctl -u backyardchirps-recorder -n 50 --no-pager
```

Usually the microphone. Check it survived a reboot with `arecord -l`, and that the right one
is chosen under **Settings → Microphone**.

A station that has never finished the setup wizard is a different case: its recorder is stopped
on purpose and the journal is empty. Open the site and it takes you back to the wizard.

Species pages show no range map and no seasonality chart: the station has no region pack, or the
one it has does not cover the coordinates. **Settings → Region pack** says which, and the section
above covers what to do about it. Detections are unaffected either way, since BirdNET reads
neither.

The whole site is unreachable:

```bash
sudo systemctl status nginx backyardchirps-web
```

Everything at once:

```bash
sudo systemctl status nginx backyardchirps-web backyardchirps-recorder \
    backyardchirps-update-species.timer backyardchirps-clip-disk-quota.timer
```
