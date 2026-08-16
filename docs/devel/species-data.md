# Species data

The taxonomy, the per-species assets, and the location lists that fit the app to wherever it is
running. It all lives under `backyardchirps/species_data/`.

Everything here divides into **global and location-specific**. A photo of a bird, a worldwide
occurrence raster and the BirdNET taxonomy are the same everywhere, so they are shared and never
copied per location. Which species can be heard, and a range map drawn around your part of the
world, change from one country to the next.

## Layout

```
backyardchirps/species_data/
├── taxonomy/
│   └── birdnet_taxonomy.json     GLOBAL. Common names, eBird codes, and Wikipedia
│                                 links for every species BirdNET knows.
├── assets/                       GLOBAL, keyed by slug
│   ├── images/                   One photo per species (<slug>.jpg)
│   └── ebird_occurrence/         eBird Status & Trends rasters, one folder per
│                                 species (named by eBird code): a worldwide 9km
│                                 raster plus band-dates.csv, sampled at your
│                                 lat/lon for the seasonality timeline. Large,
│                                 git-ignored, re-downloadable.
├── locations/
│   └── <slug>/                   One directory per location
│       └── range_maps/           <slug>.webp, framed on this region
└── generated/                    GIT-IGNORED, written at runtime
    ├── taxonomy/                 The refreshed taxonomy
    └── species_birdnet.txt       The station's own species list, derived from
                                  its coordinates
```

`ACTIVE_LOCATION` picks the `locations/<slug>/` directory the app reads. It defaults to `spain`
in `backyardchirps/settings/django_settings.py`, and the environment variable of the same name
overrides it. Range maps are all it selects: the species list under `generated/` is named after
nothing, because it belongs to the station's coordinates rather than to a region.

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

## Adding a location

Everything under `assets/` is global, so a new location reuses the photos and rasters already
present. The only thing it needs of its own is range maps, since those are drawn around a
region. The species list is not part of this: a station generates its own.

**1. Set the coordinates.** In the app settings or the Django admin, point `LOCATION_LAT` and
`LOCATION_LON` at the new recording site.

**2. Create the directory** and select it:

```bash
mkdir -p backyardchirps/species_data/locations/<slug>/range_maps
export ACTIVE_LOCATION=<slug>        # or change the default in django_settings.py
```

This selects the range maps and nothing else.

**3. Generate the species list.** This refreshes the taxonomy, then asks GeoModel which
species are plausible at the configured coordinates in any week of the year, and writes them
under `generated/`:

```bash
uv run python manage.py update_species_data
```

**4. Get the occurrence rasters and the range maps.** Both come from eBird Status & Trends, and
neither is fetched from this repository any more: they are what a **region pack** carries, and
the tooling that downloads, crops and draws them lives in
[tapia/backyardchirps-regional-packs](https://github.com/tapia/backyardchirps-regional-packs)
along with an eBird access key.

The quickest path is to build a pack for a box around the new location and unpack it. Point
`EBIRD_DATA_DIR` at its `ebird_occurrence/` and `SPECIES_RANGE_MAPS_DIR` at its `range_maps/`,
or copy the contents into the directories above.

Rasters are keyed by eBird code and are the same everywhere, so any species you already have is
reused. Range maps are framed on one box and cannot be shared between regions.

**5. Species photos are optional.** `assets/images/` is global; add any missing `<slug>.jpg` if
you have one. Without it the app falls back to the BirdNET image API.

**6. Restart the recorder.** The analyzer reads the coordinates only at startup, so `run_recorder`
has to be restarted after changing the location or the coordinates.
