# Species data

The taxonomy and the per-species assets that fit the app to wherever it is running. It all lives
under `backyardchirps/species_data/`.

Everything here is the same everywhere. A photo of a bird and the BirdNET taxonomy do not change
from one country to the next, so they ship with the code. The two things that do, range maps and
occurrence rasters, come from a **region pack** the station downloads for its own part of the
world, and nothing in the repository is named after a country.

## Layout

```
backyardchirps/species_data/
├── taxonomy/
│   └── birdnet_taxonomy.json     SHIPPED. Common names, eBird codes, and Wikipedia
│                                 links for every species BirdNET knows.
├── assets/
│   ├── images/                   SHIPPED. One photo per species (<slug>.jpg)
│   └── ebird_occurrence/         GIT-IGNORED. eBird Status & Trends rasters, one
│                                 folder per species (named by eBird code): a 9km
│                                 raster plus band-dates.csv, sampled at your
│                                 lat/lon for the seasonality timeline.
└── generated/                    GIT-IGNORED, written at runtime
    ├── taxonomy/                 The refreshed taxonomy
    ├── species_birdnet.txt       The station's own species list, derived from
    │                             its coordinates
    └── range_maps/               A link into the installed region pack, holding
                                  <slug>.webp framed on that pack's box
```

Installing a pack writes `range_maps` and `ebird_occurrence` as symlinks into it, so the paths in
`django_settings.py` never change and nothing has to know which pack is in use. A station with no
pack has neither directory, which is a working state: species pages lose the range map and the
seasonality timeline, and everything else behaves as usual.

One thing to know when installing a pack in a checkout rather than on a station. Both links are
written under `generated/`, and `SPECIES_RANGE_MAPS_DIR` reads from there, but `EBIRD_DATA_DIR`
in a checkout is still `assets/ebird_occurrence`, which is where a development machine has always
kept its rasters. So a locally installed pack gives you its range maps, and its rasters need
`EBIRD_DATA_DIR` pointing at them or their contents copied across.

## The seed and the generated files

Only `birdnet_taxonomy.json` is a **seed**: it ships in the repository so tests, CI and fresh
installs always have a taxonomy to work from.

The species list is not, and nothing ships one. A station builds its own under `generated/` from
its own coordinates, so a list is only ever right for the station that made it. Committing one
would describe wherever it happened to be generated, which for anybody else is worse than having
none. A station with no list yet searches the whole taxonomy and reports nothing as rare, both of
which are working states.

`update_species_data` (a daily timer in production) writes only under `generated/`, never over
the committed taxonomy, so a `git pull` on deploy cannot conflict.

The list used to sit under `generated/locations/<slug>/`. A station updating across that change
finds no list at the new path and behaves as a station that never had one, which is a working
state, until the daily timer writes a fresh one. Run `update_species_data` by hand to skip the
wait.

The two sit on opposite sides of the code and data split in [architecture.md](architecture.md).
The seed ships with the release. When `BACKYARDCHIRPS_DATA_DIR` is set, the generated files move to
`$BACKYARDCHIRPS_DATA_DIR/species/`, the models to `$BACKYARDCHIRPS_DATA_DIR/models/` and the eBird rasters to
`$BACKYARDCHIRPS_DATA_DIR/species/ebird_occurrence/`, so an update never downloads them again. With it
unset they stay in the tree above.

**Provenance.** The taxonomy comes from the BirdNET API. Occurrence rasters and range-map source
data come from [eBird Status & Trends](https://science.ebird.org/en/status-and-trends). Photos
come from the BirdNET image API, with an in-app fallback when a local `<slug>.jpg` is missing.

## Moving a station to a new location

Nothing in the repository has to change. Everything that belongs to one part of the world is
either derived from the coordinates or carried by a pack.

**1. Set the coordinates.** In the app settings or the Django admin, point `LOCATION_LAT` and
`LOCATION_LON` at the new recording site.

**2. Install the pack that covers them.** The settings page has a card for it, which resolves the
coordinates against the pack index and downloads the one that matches. Moving the coordinates
offers a new pack rather than switching on its own, so a station near the edge of its box does not
re-download hundreds of megabytes because somebody nudged the pin.

Nothing in the database is keyed to a pack, so switching one changes what a species page can draw
and nothing about the history.

**3. Generate the species list.** The wizard does this when it finishes and a daily timer keeps it
fresh, so this is only for a location that has just changed. It refreshes the taxonomy, then asks
GeoModel which species are plausible at the configured coordinates in any week of the year, and
writes them under `generated/`:

```bash
uv run python manage.py update_species_data
```

**4. Species photos are optional.** `assets/images/` ships with the code and is the same
everywhere; add any missing `<slug>.jpg` if you have one. Without it the app falls back to the
BirdNET image API.

**5. Restart the recorder.** The analyzer reads the coordinates only at startup, so `run_recorder`
has to be restarted after changing them.

## When no pack covers a location

The station offers the nearest pack and a link to an issue template asking for a new one. Building
it is a job for [tapia/backyardchirps-regional-packs](https://github.com/tapia/backyardchirps-regional-packs),
which holds the builder, the range-map renderer and the eBird access key. Nothing about a pack is
built on a station, and this repository has no tooling for it: see
[releases.md](releases.md) for the build.

Rasters are keyed by eBird code and are the same everywhere, so a species that two packs both
cover costs its rasters twice, once per pack. Range maps are framed on one box and cannot be
shared between regions at all.
