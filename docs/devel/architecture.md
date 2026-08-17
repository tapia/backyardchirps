# Architecture

## Two processes, one database

```
┌─────────────────┐         ┌─────────────────┐
│   run_recorder  │         │    runserver    │
│                 │         │                 │
│ mic → BirdNET   │         │  REST API for   │
│ → filters       │         │  the Vue SPA    │
└────────┬────────┘         └────────┬────────┘
         │                           │
         └──────────┬────────────────┘
                    ▼
              detections.db (SQLite)
```

They share nothing but the database file. The recorder never serves HTTP, the web server never
touches audio, and either can restart without the other noticing. That is what makes deploys
cheap: the web server restarts on every push while the recorder keeps listening.

The one thing to remember is that **the recorder reads its configuration only at startup**. It
builds its analyzer once from `active_acoustic_model`, latitude, longitude and
`analysis_low_confidence` (`run_recorder.py`), so changing any of those in the web UI never
reaches the running process. Every other setting is read on each request.

## Local setup

Requires Python 3.13+, [uv](https://docs.astral.sh/uv/), Node.js 18+, and `gettext` for the
message catalogs. That floor is the version Raspberry Pi OS trixie ships, since a station builds
against the system interpreter.

`uv sync` gives you everything, BirdNET 2 and TensorFlow included, because the dev group asks
for the `birdnet2` extra so the tests can exercise both models. A station installs neither
unless it is set to BirdNET 2.

```bash
uv sync
cp .env.example .env              # SECRET_KEY is the only required value
uv run python manage.py migrate
uv run python manage.py compilemessages --ignore .venv --ignore frontend
uv run python manage.py runserver
```

### Translations

The `.po` files under `backyardchirps/locale/` are the source and are tracked. The `.mo` files
gettext actually reads are built from them and are not, so a fresh checkout is English until you
compile them, which is the line above. After changing a translated string, run
`uv run python manage.py makemessages -l <code> --no-obsolete`, fill in the new entries, and let
the pre-commit hook recompile: it runs whenever a `.po` changes, so a stale catalog cannot
survive a commit. On a station `apply.sh` compiles them on every deploy.

Nothing in the build names a language. `compilemessages` takes whatever `locale/` holds and the
container test counts `.mo` files against `.po` files, so adding a language is a `makemessages`
run and a translator, with no deploy change to remember. The wizard's own picker is the one place
a language has to be listed, in `LANGUAGE_OPTIONS`.

A number drawn into a form field needs `{% localize off %}`. Spanish writes `0,7` for `0.7`, and
the setup wizard posts those fields straight back to a parser that reads them with `float()`.

```bash
cd frontend && npm install && npm run dev
```

Vite serves on `http://localhost:5173` and proxies `/api` to Django on 8000. Work on the
frontend, the API, or the database needs nothing more.

Recording needs a microphone:

```bash
uv run python manage.py run_recorder
```

If it picks the wrong input, choose the right one under **Microphone** on the settings page.
The recorder reads it at startup, so restart it after changing it.

## Management commands

| Command | Purpose |
|---|---|
| `run_recorder` | The capture and analysis loop |
| `update_species_data` | Downloads a fresh taxonomy, then rebuilds the local species list from GeoModel (daily timer in production) |
| `download_birdnet3_model` | Fetches the acoustic model and GeoModel when the local copy is missing or no longer the published size |
| `enforce_clip_disk_quota` | Deletes the oldest clip files when disk usage exceeds the configured percentage |

## Backend layout

The backend is organized by **feature**, not by technical layer. Each feature is a vertical
slice under `backyardchirps/features/` holding its own views, queries, workflows, and entity.
There is no `api/`, `domain/`, `repositories/`, `services/`, or `use_cases/` layer.

| Feature | Owns |
|---|---|
| `species` | The catalogue: detail, list, search, seasonality, assets, and the taxonomy itself |
| `detections` | The detection feed, validation, clip serving, disk-quota pruning |
| `overrides` | Per-species blacklist and auto-confirm threshold |
| `analytics` | Chart aggregations: timelines, heatmaps, hourly, yearly, 24h |
| `recording` | Audio capture and the acoustic model pipeline (the recorder process) |
| `notifications` | Notification rules and the notifier |
| `settings` | `AppSetting` reads and writes, with parsing and defaults |
| `setup` | The first-run wizard: the one-time token, the first admin account, the microphone picker. The only feature that renders HTML |
| `weather` | Current weather and sunrise/sunset, both cached |
| `auth`, `server_status` | Session endpoints, and the machine metrics behind the status page |

Four packages sit outside the features:

| Package | Holds |
|---|---|
| `models/` | The Django ORM schema, one app, shared on purpose: `DetectedSpecies` is a foreign-key target for both detections and overrides |
| `integrations/` | Every call to an external system, and the only place external URLs and API keys appear |
| `shared/` | Helpers that belong to no single feature: request parsing, slug resolvers, disk usage, the recorder heartbeat |
| `management/commands/` | Thin CLI entry points that call into a feature. Django looks for commands only here |

### The layering

Dependencies flow outside in, and the import graph must stay acyclic.

| Module | Does | May import |
|---|---|---|
| `views.py` | Parse the request, call queries or logic, serialize the response. No `Model.objects.*`, no business logic. Translate `ObjectDoesNotExist` to `NotFound` | queries, logic, entities, `shared/`, `integrations/` |
| `queries.py` | The only place that touches `models/`. Returns entities or plain data, never a `QuerySet` or model instance, so callers need no Django | `models/`, entities, `shared/`, settings, another feature's queries |
| `logic.py` | A named workflow spanning more than one feature. Only `overrides`, `recording`, `notifications` and `settings` need one | queries, entities, settings |
| `entity.py` | A frozen dataclass carrying the shared language between modules, plus entity-level behaviour | sibling entities and `species/taxonomy.py`, nothing else |

Two consequences of this are easy to break:

**Building a `Species` checks its scientific name against the taxonomy**, so holding one proves
the name is real. Resolve untrusted input (URL slugs, request bodies, BirdNET labels) with
`Species.from_slug()` or `Species.from_scientific_name()`, which return `None` for unknown
names, and never pass a raw scientific-name string between modules.

**`detections/queries` imports `overrides/queries`**, so overrides cannot import detections at
module load. That is why the override workflow that clears the pending queue lives in
`overrides/logic.py` rather than on the `StoredSpeciesOverride` model.

### The setup wizard is server-rendered

Every other feature answers JSON and the Vue app draws it. `setup` is the exception: it serves
HTML from `templates/setup/`, one page per step, at `/setup/`. nginx proxies that prefix to
Django like `/api/` and `/admin/`.

The flow is a URL and a session, nothing else. `GET /setup/` redirects to the step you are on,
each step POSTs to its own URL and redirects to the next, and the furthest step reached is in
the session. So a reload repeats nothing, the back button works, and closing the browser
half way through loses at most the step being filled in.

The answers go in the session too, and nothing is written to the database until the last step,
where `complete()` saves them all, deletes the token and starts the recorder. A wizard nobody
finished therefore leaves the station exactly as it was, which is what the Finish button says
and what lets the whole thing be walked through on a development machine. Each step still
checks its own fields as they arrive, through `Settings.parse`, so a bad value is refused on
the step that asked for it rather than at the end where there is nowhere to send anybody back
to.

Which is the point. The wizard was a Vue component holding the current step in memory while
the server decided separately whether setup was finished, and the two could disagree. An
install interrupted before it wrote the token was enough: the account step created the
account, the step never advanced, and the station then looked finished to the server while
having no coordinates and a stopped recorder, with no way back in through the UI.

Two endpoints survive as JSON because the SPA calls them: `setup/status/`, which the router
guard reads to decide whether to send a visitor to `/setup/` at all, and `setup/audio-devices/`,
which the settings page reuses. The level meter on the microphone step reads
`setup/audio-level/`, the one part of the wizard a page load cannot do.

That one is a stream of server-sent events rather than something to poll, and the reason is
worth knowing before anyone turns it back into a request per reading. Each reading covers a
tenth of a second, and the device stays open for the whole stream, so nothing that happens in
front of the microphone falls between two readings. Polling opened the device once per
request, which left it shut in between, and on a Pi 3 a round trip outlasted the interval, so
two readings met on a device that ALSA gives to one process at a time and one of them failed
as busy. Both faults look the same from the outside: a microphone that seems not to work.

Three things hold that up. `stream_input_levels` in `recording/audio/devices.py` closes the
device in a `finally`, which is what hands it back when the browser goes away mid-stream. The
stream stops after five minutes and the browser opens the next one, so a tab left on the step
does not hold the microphone all day. And nginx buffering is off for that one location, since
buffered readings would arrive in bursts.

A station is set up once it has an admin and no longer has a token. `install.sh` writes that
token as soon as the data directory exists, before the slow part of the install, so a failure
in between cannot leave a station whose missing token means "finished" when it means "never
written".

One exception, and the reason a checkout can be set up at all: a session that is already
walking the wizard carries on to the end even after the station counts as finished. A checkout
never had a token, so it becomes "finished" the moment the account step runs, and without this
the wizard would stop there, one step short of the coordinates and two short of the Finish that
starts the recorder.

## The audio pipeline

```
AudioRecorder → acoustic model → discard_blacklisted() → discard_non_birds() → ConsistencyFilter
    → process_confirmed_detection()
        → detections.queries.upsert()
        → Notifier.maybe_notify()
```

`AudioRecorder` keeps a rolling buffer and emits a clip every `step_duration` seconds. With the
defaults in `app_settings.py` that is a 3-second clip every 1.5 seconds, so consecutive clips
overlap by half. `clip_duration` is effectively fixed: both models score 3-second windows and
give unreliable results on anything else.

`ConsistencyFilter` holds the last `window_size` clips and confirms a species that appears in
`min_detections` of them, or scores `bypass_confidence` or above in a single clip (3, 2 and
0.8). Confirmation by repetition joins the clips involved into one `AudioClip`, so reviewers
hear the whole sequence. A bypass keeps only the clip that triggered it, to avoid mixing in
unrelated audio. The class docstring has worked examples.

Blacklisted species and non-birds are dropped between analysis and the filter, so they cost
nothing further on and other species in the same clip are unaffected. Non-birds matter more than
you might expect: BirdNET's taxonomy covers thousands of insects, mammals, amphibians and
reptiles alongside the birds, and each resolves to a valid `Species` just like a bird. Only the
detection path is filtered, so the raw candidate list stored on the detection still shows them.

The user-facing account of all this is in [using the site](../using-the-site.md).

### Choosing a model

`build_acoustic_model` (`recording/audio/acoustic_model.py`) constructs the analyzer named by
`active_acoustic_model`, read once at recorder startup. Each model lives in its own package and
both satisfy the `AcousticModel` protocol (`analyze(clip) -> Analysis`, bundling the resolved
`results` that feed the pipeline with the full `raw_candidates` kept for the record).

| `active_acoustic_model` | Implementation | Location filter |
|---|---|---|
| `birdnet_3` (default) | `BirdNet3Analyzer`, the V3 acoustic ONNX | GeoModel 3 (`birdnet3/geomodel.py`) |
| `birdnet_2` | `BirdNet2Analyzer`, birdnetlib | birdnetlib's own `SpeciesList` |

The factory imports each analyzer inside its own branch, so only the chosen model's
dependencies are loaded: BirdNET 3 brings in onnxruntime but never birdnetlib or TensorFlow, and
BirdNET 2 never brings in onnxruntime.

BirdNET 3 is still a preview release, which is why BirdNET 2 remains as the fallback. Both models
score on similar scales at the same floors, so the thresholds carry over untouched.

BirdNET 2 is an optional extra rather than a dependency, since only its analyzer imports
birdnetlib and that import is lazy. Leaving it out takes a production install from 98 packages to
68, TensorFlow being most of the difference. Going back to it is a settings change,
`uv sync --no-dev --extra birdnet2`, and a recorder restart. `apply.sh` reads the setting after
migrating and installs the extra itself when it finds `birdnet_2`, so a station already on
BirdNET 2 keeps working across a deploy. Select it without installing it and the factory refuses
to build an analyzer, which stops the recorder at startup with the command to run.

Two things to know about BirdNET 3 on a Pi. It is heavy: a large fp32 ONNX needing a comparable
amount of extra RAM, and slower inference, against a clip arriving every 1.5 s. And its
`predictions` output has already been through a sigmoid, so the analyzer takes it as the
confidence as it is. BirdNET's own tooling applies a second sigmoid, which would squeeze every
score into the range 0.5 to 0.73.

GeoModel 3 is a small ONNX that turns `[latitude, longitude, week]` into an occurrence
probability per species, which limits BirdNET 3 to the species plausible at the station that
week. `geomodel_threshold` (0.03) is the probability at which a species counts as present.
BirdNET V3 publishes no recommended value, so tune it by observation. With no location
configured, BirdNET 3 runs unfiltered. The acoustic model and GeoModel ship different label
sets, so species are matched by `Species` identity rather than by class index.

Both BirdNET 3 files are global rather than per-location and are git-ignored, downloaded by
`download_birdnet3_model` (Zenodo for the acoustic model, a GitHub release for GeoModel) on
every deploy before the recorder restarts. A file comes down only when it is missing or its
size differs from the published one, which is also how a station moves to a newer GeoModel.

### What a detection carries

`recorded_at` is the moment the audio was captured, and it is the site's whole time axis: every
chart, filter, count, and displayed time reads it.

It also identifies the clip, so **two rows sharing a `recorded_at` came from the same clip**.
Every species heard in one clip gets its own row and its own clip file, matching only on that
instant, which is what stops one bird being counted twice. Nothing may put two unrelated rows on
the same instant.

The batch window has no column of its own. `get_block_time()` rounds a moment down to
`detection_time_buffer_in_minutes` (3), `upsert` keeps one row per species per window and
replaces the clip when a more confident hit arrives, and the notifier holds a detection until
its window closes. Rounding down never crosses an hour, since 60 divides by the window.

Each detection also records `analysis_time_ms` and the clip's full `analysis_candidates`, taken
from the clip where the species scored highest. Both are empty on rows written before these
fields existed.

### The reassign guard

`species_identified_in_same_recording()` gives the review dialog the other species a recording
was identified as, so it can disable them in the reassign search and stop a reviewer creating a
duplicate. It reads saved detections rather than `analysis_candidates`, because a label the
pipeline scored and threw away was never an identification. Blacklisted species are left out.

Only the detail endpoint calls it, and `also_identified` appears only there, since the dialog
opens one detection at a time and fetches its own. `confirm()` applies the same rule on the
server, raising `SpeciesAlreadyIdentified` (a 400) and changing nothing. It has to: the endpoint
accepts any species name, and the dialog is not the only way to reach it.

## Tests

```bash
uv run pytest                        # everything, with coverage
uv run pytest tests/unit             # fast, no database
uv run pytest tests/integration      # ORM and endpoints
uv run pytest -o addopts="" tests/…  # skip the coverage report
```

The split is mechanical: **if it needs the database or the filesystem it is integration,
otherwise it is unit.** Integration tests run against in-memory SQLite and replace every network
and hardware call with a stub, so the real `detections.db` is never touched and the suite works
offline.

`tests/` mirrors `backyardchirps/`, so a feature's tests live in `tests/unit/features/<feature>/`
and `tests/integration/features/<feature>/`. Endpoint and permission tests go in
`tests/integration/api/`. Unit fixtures are in `tests/conftest.py`, integration fixtures (DB
builders, HTTP clients) in `tests/integration/conftest.py`. Test-only code may import
`backyardchirps.models` directly to arrange state.

One test sits outside that mirror, because what it tests is not in `backyardchirps/`.
`tests/unit/test_preflight.py` runs `install.sh --preflight-only` against fixture files in a
temporary directory, which is the only way to reach the installer's hardware checks: the
container test is not a Raspberry Pi, and the one machine that is cannot be a fixture. It writes
files, so the rule above would make it an integration test, but it needs no database and finishes
in well under a second, so it stays with the fast suite. See
[deployment.md](deployment.md).

One trap: `tests/` has no `__init__.py`, which is what pytest's import mode needs. The result is
that **every test filename must be unique across the whole suite**. Two files named
`test_queries.py` in different features collide. Qualify them: `test_detection_queries.py`.

### The environment a test run sees

`django_settings.py` calls `load_dotenv()` while it is imported, so a `.env` in the checkout
reaches the tests. Two things follow.

**Credentials are blanked in `tests/conftest.py`.** Migration 0002 copies `TELEGRAM_TOKEN`,
`TELEGRAM_CHAT_ID` and `XENO_CANTO_API_KEY` into `AppSetting` rows when the test database
is built. Without the blanking, a developer with real credentials
would run the suite against a database holding them, and row counts would differ from one
machine to the next. That works because migrations run long after conftest is imported.

**Anything read at settings-import time cannot be pinned from a conftest.** pytest-django
calls `django.setup()` from `pytest_load_initial_conftests`, before any conftest is imported,
so `SECRET_KEY`, `DEBUG` and `BACKYARDCHIRPS_DATA_DIR` are already decided by then. `SECRET_KEY` has
to come from the real environment: `.env` locally, and the `SECRET_KEY` value the CI workflow
sets. Setting it in a conftest has no effect.

## Linting

```bash
uv run ruff check backyardchirps --fix
uv run ruff format backyardchirps
uv run mypy backyardchirps

cd frontend && npx eslint src --quiet && npx prettier --check src && npm run build

shellcheck --severity=style install.sh uninstall.sh deploy/*.sh
```

All of it runs as pre-commit hooks and again in CI (`.github/workflows/ci.yml`) on every push
and pull request, in three jobs: backend, frontend and shell. To run the hooks by hand:
`pre-commit run --all-files`.

The frontend build is checked as well as linted, because a release ships the frontend already
compiled, so a build that fails would otherwise only be found when a tag is pushed.

mypy runs with `allow_untyped_defs = false`, so every function needs a type annotation,
including the return type. A view is `(request: Request, …) -> Response`.

## Code and data

The rest of this page is about a running station rather than a development machine.

Code and collected data live in separate directories, so a whole release can be replaced
without touching anything the station has gathered:

| | Holds | Lifetime |
|---|---|---|
| `BASE_DIR` | The code: Python, the built frontend, `deploy/`, species seeds | One per release, disposable |
| `DATA_DIR` | `.env`, `detections.db`, `clips/`, `staticfiles/`, downloaded models, `packs/` | Never replaced |

The two directories have different owners, which is what decides where a deploy step can run.
`BASE_DIR` belongs to root, which is what installs it. `DATA_DIR` belongs to the
`backyardchirps` system user, which is what the four systemd units run as, so a station's data
has one owner whatever put it there. `apply.sh` runs as root and drops to the service user
through `run_as_service_user` for everything that touches `DATA_DIR`, including reading `.env`.

`collectstatic` is why `STATIC_ROOT` is in `DATA_DIR` rather than next to the code: it runs as
the service user like every other `manage.py` command, and writing to the code directory would
need a root step on every deploy to hand the output directory over. The trade is that static
files from an older release are not pruned.

`DATA_DIR` comes from `BACKYARDCHIRPS_DATA_DIR`. It has to be a real environment variable, never a line
in `.env`, because `.env` is itself read out of the directory it names. Three readers need it,
and each gets it from somewhere different:

| Reader | Gets it from |
|---|---|
| The running services | `Environment=` in each systemd unit, written when `apply.sh` renders it |
| `apply.sh`, when its caller passes nothing | `/etc/default/backyardchirps` |
| `manage.py` run by hand | the operator's shell profile |

Only the first is written automatically. `provision-data-dir.sh` sets up the other two during
installation. `apply.sh` refuses to run when none of them says where the data is, rather than
guessing: a guess would migrate a fresh empty database somewhere and leave the real one
orphaned.

On a development machine there is no `BACKYARDCHIRPS_DATA_DIR` and `DATA_DIR` falls back to
`BASE_DIR`, so everything lands inside the checkout. That is `django_settings.py` doing it, not
`apply.sh`, which never runs on a development machine at all.

Species data falls on both sides. The committed taxonomy and photos ship with the code. The
regenerated copies, the models and everything a region pack carries are downloaded on the machine
and stay with the data, so an update never fetches them again. See
[species-data.md](species-data.md).

```
/var/lib/backyardchirps/
├── .env  detections.db  recorder_heartbeat.json
├── clips/
├── models/         BirdNET 3 acoustic model and GeoModel
├── species/        taxonomy/, species_birdnet.txt, and the range_maps/ and
│                   ebird_occurrence/ links into the installed pack
└── region-packs/   one directory per downloaded pack
```

In a checkout, all of it sits under `backyardchirps/species_data/` instead.

## Deploying

`deploy/apply.sh` is the whole build, and it never fetches code: whatever calls it puts the code
on disk first. It runs as root against an unpacked release and only that, so there is one shape
of machine to reason about rather than three. `install.sh` is the caller today. Every step can be
repeated safely, which is why one script both sets up a new machine and updates a running one.

A station never runs from a git checkout, including yours. To put your own build on a Pi, make a
release and install it: [deployment.md](deployment.md) covers both the automatic path and the
manual one.

## Where else to look

| | |
|---|---|
| [frontend.md](frontend.md) | The Vue app |
| [species-data.md](species-data.md) | Taxonomy, assets, and adding a location |
| [releases.md](releases.md) | Cutting a version and what ships in one |
| [deployment.md](deployment.md) | Getting a build onto your own Pi, and testing an install |
| [installation.md](../installation.md) | Installing a release, the path a user takes |
