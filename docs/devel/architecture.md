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

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node.js 18+.

`uv sync` gives you everything, BirdNET 2 and TensorFlow included, because the dev group asks
for the `birdnet2` extra so the tests can exercise both models. A station installs neither
unless it is set to BirdNET 2.

```bash
uv sync
cp .env.example .env              # SECRET_KEY is the only required value
uv run python manage.py migrate
uv run python manage.py runserver
```

```bash
cd frontend && npm install && npm run dev
```

Vite serves on `http://localhost:5173` and proxies `/api` to Django on 8000. Work on the
frontend, the API, or the database needs nothing more.

Recording needs a microphone:

```bash
uv run python manage.py run_recorder
```

If it picks the wrong input, list devices with `python -m sounddevice` and set `AUDIO_DEVICE` to
the index you want.

## Management commands

| Command | Purpose |
|---|---|
| `run_recorder` | The capture and analysis loop |
| `update_species_data` | Downloads a fresh taxonomy, then rebuilds the local species list from GeoModel (daily timer in production) |
| `download_birdnet3_model` | Fetches the acoustic model and GeoModel when their checksums change |
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
| `weather` | Current weather and sunrise/sunset, both cached |
| `auth`, `server_status` | Session endpoints, and the machine metrics behind the status page |

Four packages sit outside the features:

| Package | Holds |
|---|---|
| `models/` | The Django ORM schema, one app, shared on purpose: `DetectedSpecies` is a foreign-key target for both detections and overrides |
| `integrations/` | Every call to an external system, and the only place external URLs and API keys appear |
| `shared/` | Helpers that belong to no single feature: request parsing, slug resolvers, disk usage, checksums |
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
`download_birdnet3_model` (Zenodo for the acoustic model, Hugging Face for GeoModel) on every
deploy before the recorder restarts.

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

One trap: `tests/` has no `__init__.py`, which is what pytest's import mode needs. The result is
that **every test filename must be unique across the whole suite**. Two files named
`test_queries.py` in different features collide. Qualify them: `test_detection_queries.py`.

## Linting

```bash
uv run ruff check backyardchirps --fix
uv run ruff format backyardchirps
uv run mypy backyardchirps

cd frontend && npx eslint src --quiet && npx prettier --check src
```

All of it runs as pre-commit hooks and again in CI (`.github/workflows/ci.yml`) on every push
and pull request. To run the hooks by hand: `pre-commit run --all-files`.

## Code and data

The rest of this page is about a running station rather than a development machine.

Code and collected data live in separate directories, so a whole release can be replaced
without touching anything the station has gathered:

| | Holds | Lifetime |
|---|---|---|
| `BASE_DIR` | The checkout: Python, the built frontend, `deploy/`, species seeds | One per release, disposable |
| `DATA_DIR` | `.env`, `detections.db`, `clips/`, `staticfiles/`, downloaded models, `packs/` | Never replaced |

The two directories have different owners, which is what decides where a deploy step can run.
`BASE_DIR` belongs to whoever deploys. `DATA_DIR` belongs to the `backyardchirps` system user,
which is what the four systemd units run as, so a station's data has one owner however many
people deploy. `apply.sh` builds the code as the deploying user and drops to the service user
through `run_as_service_user` for everything else, including reading `.env`.

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
| `apply.sh`, on the next deploy | `/etc/default/backyardchirps` |
| `manage.py` run by hand | the operator's shell profile |

Only the first is written automatically. The other two are set up once during installation, and
the middle one is load-bearing: a CI deploy carries none of the operator's environment, so
without that file `apply.sh` falls back to the checkout and migrates a fresh empty database
into it.

**Leave `BACKYARDCHIRPS_DATA_DIR` unset and `DATA_DIR` becomes `BASE_DIR`**, putting everything inside
the checkout. That is what a development machine wants.

Species data falls on both sides. The committed taxonomy, photos and per-location seeds ship
with the code. The regenerated copies and the eBird rasters are downloaded on the machine and
stay with the data, so the models survive an update instead of being downloaded again. See
[species-data.md](species-data.md).

```
/var/lib/backyardchirps/
├── .env  detections.db  recorder_heartbeat.json
├── clips/
├── models/     BirdNET 3 acoustic model and GeoModel
├── species/    taxonomy/, locations/<slug>/, ebird_occurrence/
└── packs/      region packs
```

In a checkout, all of it sits under `backyardchirps/species_data/` instead.

## Deploying

`deploy/apply.sh` is the whole build, and it never fetches code: whatever calls it puts the code
on disk first. Today that caller is `deploy/deploy.sh`, run by GitHub Actions on every push to
main. Every step can be repeated safely, which is why one script both sets up a new machine and
updates a running one.

[installation.md](../installation.md) lists what a deploy does, step by step.

## Where else to look

| | |
|---|---|
| [frontend.md](frontend.md) | The Vue app |
| [species-data.md](species-data.md) | Taxonomy, assets, and adding a location |
| [releases.md](releases.md) | Cutting a version and what ships in one |
| [installation.md](../installation.md) | Production deployment |
