# Admin guide

Running the station day to day. For setting up a new Pi, see
[installation.md](installation.md).

Log in at `/login` with a staff account, created during installation. **Settings**,
**Detection settings**, and **Server status** then appear under **Admin** in the navbar;
without staff access they redirect to the login page.

## Settings

### Recording station coordinates

Latitude and longitude of the microphone. BirdNET uses these to rule out species that do not
occur in the area, so a wrong value here damages every identification, with no visible sign
that anything is wrong.

### Acoustic model

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

### BirdNET analysis

Three thresholds, and only two of them change what gets recorded.

| Setting | Default | Effect |
|---|---|---|
| Low confidence | 0.4 | BirdNET's floor. Anything below is discarded and never reaches the database. |
| Medium confidence | 0.7 | The auto-confirm bar. At or above it a detection is published directly; below it, it waits for review. |
| High confidence | 0.9 | Display only. Sets what the navbar's "High" filter shows. |

Raising **Low** means fewer detections overall and a quieter site. Raising **Medium** means the
same detections, with more of them queued. If the review queue has more in it than you can get
through, lower Medium. If rubbish is reaching the public pages, raise it.

### Storage

Recordings pile up forever unless you set a limit. **Maximum disk usage** is a percentage of
the disk holding the clips folder, 85% by default. Whenever usage goes above it, a scheduled
job deletes the audio of the oldest clips.

Only the audio goes. The detection records stay, so history, charts and species counts are
unaffected. The old entries simply lose their play button.

### Notifications

Telegram messages, if `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are set in `.env`. Each rule has
its own switch and its own minimum confidence, so you can be strict about what is worth being
interrupted for.

| Rule | Default confidence | Fires when |
|---|---|---|
| New species | 0.9 | A species is detected for the very first time |
| First today | 0.9 | First detection of a species today |
| First this year | 0.9 | First detection of a species this calendar year |
| Rare species | 0.75 | A species that rarely turns up here is heard |
| Long absent | 0.9 | A species returns after 30+ days (configurable) |
| Pending validation | n/a | Something landed in the review queue |

Messages go out in Spanish by default; change it under **Send messages in**.

### What needs a recorder restart

Settings live in the database and take effect at once, with three exceptions. The recorder
builds its analyzer only when it starts, so the coordinates, the acoustic model and the low
confidence threshold are read once and then kept. Changing any of those needs:

```bash
sudo systemctl restart backyardchirps-recorder
```

Everything on this page not in that list takes effect on the next page load.

## Per-species detection rules

Some species get reported far more often than they actually occur. Two overrides deal with
that, reachable from **Settings → Customized species**, from a species' own page, or inside
the review dialog. Both work only on species heard here at least once. Anyone can see the rules
in place, but only admins can change them.

**A custom auto-confirm threshold** replaces the global 0.7 bar for one species. A bird that
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

Usually the microphone. Check it survived a reboot with `arecord -l`.

The whole site is unreachable:

```bash
sudo systemctl status nginx backyardchirps-web
```

Everything at once:

```bash
sudo systemctl status nginx backyardchirps-web backyardchirps-recorder \
    backyardchirps-update-species.timer backyardchirps-clip-disk-quota.timer
```
