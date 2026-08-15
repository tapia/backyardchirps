import csv
import io
import logging
from pathlib import Path

from backyardchirps.integrations import github
from backyardchirps.integrations import zenodo

logger = logging.getLogger(__name__)


def refresh_birdnet3_model(model_destination: Path, labels_destination: Path) -> list[str]:
    """
    Download the BirdNET 3 model and its labels from Zenodo, and return the names of the
    files that were actually written.

    The model comes down only when the local copy is missing or its size differs from
    the published one, so this is cheap to run on a schedule. A running recorder stays
    on the model it loaded at startup and has to be restarted to pick up a new one.
    """
    written = []

    if _has_published_size(model_destination, zenodo.BIRDNET3_MODEL_SIZE):
        logger.info("BirdNET 3 model is up to date")
    else:
        zenodo.download_file(zenodo.BIRDNET3_MODEL_URL, model_destination)
        written.append(model_destination.name)

    if labels_destination.exists():
        logger.info("BirdNET 3 labels are up to date")
    else:
        labels = _scientific_names_from_csv(zenodo.fetch_labels_csv())
        labels_destination.parent.mkdir(parents=True, exist_ok=True)
        labels_destination.write_text("\n".join(labels) + "\n")
        logger.info("Wrote %d BirdNET 3 labels", len(labels))
        written.append(labels_destination.name)

    return written


def refresh_geomodel(model_destination: Path, labels_destination: Path) -> list[str]:
    """
    Download the GeoModel 3 model and its labels from the release that publishes them,
    and return the names of the files that were actually written.

    A file comes down only when the local copy is missing or its size differs from the
    published one, so this is cheap to run on a schedule, and a station carrying an
    earlier GeoModel picks the new one up on the next deploy. The labels are saved
    exactly as they arrive, one tab-separated row per class, and GeoModel picks out the
    scientific name when it loads them.
    """
    wanted = [
        (github.GEOMODEL_MODEL_URL, github.GEOMODEL_MODEL_SIZE, model_destination),
        (github.GEOMODEL_LABELS_URL, github.GEOMODEL_LABELS_SIZE, labels_destination),
    ]

    written = []
    for url, published_size, destination in wanted:
        if _has_published_size(destination, published_size):
            logger.info("GeoModel %s is up to date", destination.name)
            continue
        github.download_file(url, destination)
        written.append(destination.name)

    return written


def _has_published_size(destination: Path, published_size: int) -> bool:
    """
    Whether the local file is there and as large as the published one. Size is all these
    releases give us to compare against, and it is enough to catch both a missing file
    and a download that stopped halfway.
    """
    return destination.exists() and destination.stat().st_size == published_size


def _scientific_names_from_csv(csv_text: str) -> list[str]:
    """
    Pull the scientific names out of the BirdNET 3 label CSV, sorted by class index so
    that line N is the species for output class N.
    """
    reader = csv.reader(io.StringIO(csv_text), delimiter=";")
    header = next(reader)
    # The first field carries a UTF-8 BOM, so match the index column by suffix.
    index_column = next(column for column, field in enumerate(header) if field.endswith("idx"))
    scientific_column = header.index("sci_name")
    rows = sorted((row for row in reader if row), key=lambda row: int(row[index_column]))
    return [row[scientific_column] for row in rows]
