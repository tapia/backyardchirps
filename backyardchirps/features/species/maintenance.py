import json
import logging
from pathlib import Path

import numpy as np
from django.conf import settings

from backyardchirps.features.recording.audio.birdnet3.geomodel import GeoModel
from backyardchirps.features.species.entity import Species
from backyardchirps.integrations.birdnet import download_taxonomy

logger = logging.getLogger(__name__)

# These write to the runtime paths, never to the committed seeds. The tracked files
# therefore stay as they are and deploys never hit a conflict, while the app still picks
# up what is written here, because it prefers the runtime copies.
_TAXONOMY_FILE = settings.SPECIES_TAXONOMY_RUNTIME_FILE
_SPECIES_FILE = settings.SPECIES_LIST_RUNTIME_FILE

# Deliberately lower than the geomodel_threshold the recorder filters detections with.
# This list decides what the search offers and what counts as rare, so a bird that turns
# up here only occasionally should still be on it. Tune it by observation, the same way.
_SPECIES_LIST_THRESHOLD = 0.01

# GeoModel takes a week index, and the year is divided into 48 of them.
_WEEKS = range(1, 49)


def refresh_taxonomy() -> None:
    data = download_taxonomy()
    _TAXONOMY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_TAXONOMY_FILE, "w", encoding="utf-8") as taxonomy_file:
        json.dump(data, taxonomy_file, ensure_ascii=False, indent=2)
    logger.info("Taxonomy updated: %d entries written to %s", len(data), _TAXONOMY_FILE)


def refresh_species_list(latitude: float, longitude: float) -> None:
    """
    Ask GeoModel which species are plausible at this location at any point in the year,
    and save the list.

    Every name comes back already resolved against the taxonomy, so the list cannot name
    a species the rest of the app would then reject. That matters: a name the taxonomy no
    longer knows used to break the search and make a renamed local bird report itself as
    rare.

    Does nothing when GeoModel has not been downloaded yet. The app copes with no list at
    all, searching the whole taxonomy and reporting nothing as rare.
    """
    if not geomodel_is_available():
        logger.warning("GeoModel is not downloaded yet, so the species list was left alone")
        return

    sorted_names = plausible_species_names(latitude, longitude)
    header = (
        "# Species plausible at this station, according to GeoModel\n"
        f"# Generated with threshold={_SPECIES_LIST_THRESHOLD}, over all {len(_WEEKS)} weeks\n"
        "# Format: scientific_name (one per line)\n"
    )
    _SPECIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SPECIES_FILE, "w", encoding="utf-8") as species_file:
        species_file.write(header)
        for scientific_name in sorted_names:
            species_file.write(scientific_name + "\n")
    logger.info("Species list updated: %d species written to %s", len(sorted_names), _SPECIES_FILE)


def geomodel_is_available() -> bool:
    """
    Whether the GeoModel files have been downloaded. Until they have, nothing that needs
    them can run.
    """
    return Path(settings.GEOMODEL_MODEL_FILE).exists() and Path(settings.GEOMODEL_LABELS_FILE).exists()


def plausible_species_names(latitude: float, longitude: float) -> list[str]:
    """
    Every species GeoModel considers plausible at this point in any week of the year,
    sorted. Each one is already resolved against the taxonomy, so callers never have to
    handle a name the rest of the app would reject.

    Shared with the eBird raster downloader, so a station and the tooling always agree on
    what counts as plausible here.
    """
    return plausible_species_names_over([(latitude, longitude)])


def plausible_species_names_over(points: list[tuple[float, float]]) -> list[str]:
    """
    The same list, for every species plausible at any of these points in any week of the
    year. A station passes the one point it sits on; the region-pack builder passes a grid
    covering a bounding box, and gets the union over the whole box.

    One threshold serves both, which is the point of sharing this: a pack built here can
    never be missing a raster for a species the station at its centre would go looking
    for.
    """
    if not points:
        return []

    geomodel = GeoModel(
        model_path=Path(settings.GEOMODEL_MODEL_FILE),
        labels_path=Path(settings.GEOMODEL_LABELS_FILE),
    )
    # Kept as the element-wise maximum rather than as a growing set of species. A score
    # reaching the threshold in any week at any point is exactly a maximum reaching it,
    # and the names are resolved once at the end instead of once per run.
    runs = [(latitude, longitude, week_48) for latitude, longitude in points for week_48 in _WEEKS]
    highest_scores = geomodel.occurrence_scores(*runs[0])
    for latitude, longitude, week_48 in runs[1:]:
        highest_scores = np.maximum(highest_scores, geomodel.occurrence_scores(latitude, longitude, week_48))

    plausible: set[Species] = geomodel.species_above(highest_scores, _SPECIES_LIST_THRESHOLD)
    return sorted(species.scientific_name for species in plausible)
