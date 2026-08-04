import csv
import io
import logging
from pathlib import Path

from backyardchirps.integrations import huggingface
from backyardchirps.integrations import zenodo
from backyardchirps.integrations.huggingface import RemoteFile
from backyardchirps.shared.checksums import git_blob_sha1_of
from backyardchirps.shared.checksums import sha256_of

logger = logging.getLogger(__name__)

# The GeoModel 3 files to fetch from Hugging Face. FP16 is the only build published
# for the V3.0.2 12K set, and it costs us nothing: its tensors are still float32, so
# onnxruntime runs it on the CPU as it is, and the model is small and only runs once a
# week anyway. Keep both files on the same version, or the model's output classes stop
# matching the label rows.
_GEOMODEL_REMOTE_MODEL = "BirdNET+_Geomodel_V3.0.2_Global_12K_FP16.onnx"
_GEOMODEL_REMOTE_LABELS = "BirdNET+_Geomodel_V3.0.2_Global_12K_Labels.txt"


def refresh_birdnet3_model(model_destination: Path, labels_destination: Path) -> list[str]:
    """
    Download the BirdNET 3 model and its labels from Zenodo, and return the names of the
    files that were actually written.

    The model comes down only when the local copy is missing or its size differs from
    the published one, so this is cheap to run on a schedule. A running recorder stays
    on the model it loaded at startup and has to be restarted to pick up a new one.
    """
    written = []

    if model_destination.exists() and model_destination.stat().st_size == zenodo.BIRDNET3_MODEL_SIZE:
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
    Download the GeoModel 3 model and its labels from Hugging Face, and return the names
    of the files that were actually written.

    A file comes down only when the local copy is missing or no longer matches the
    digest Hugging Face publishes, so this is cheap to run on a schedule. The labels are
    saved exactly as they arrive, one tab-separated row per class, and GeoModel picks out
    the scientific name when it loads them.
    """
    remote_files = huggingface.list_files()
    wanted = {
        _GEOMODEL_REMOTE_MODEL: model_destination,
        _GEOMODEL_REMOTE_LABELS: labels_destination,
    }

    written = []
    for remote_name, destination in wanted.items():
        remote_file = remote_files.get(remote_name)
        if remote_file is None:
            raise FileNotFoundError(f"{remote_name} is not published in the GeoModel repository")
        if _is_up_to_date(destination, remote_file):
            logger.info("GeoModel %s is up to date", destination.name)
            continue
        huggingface.download_file(remote_file.path, destination)
        written.append(destination.name)

    return written


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


def _is_up_to_date(destination: Path, remote_file: RemoteFile) -> bool:
    """
    Whether the local file already holds the published content. Which digest we compare
    depends on which one the Hub reports: sha256 for large files, git object id for the
    rest.
    """
    if not destination.exists():
        return False
    if remote_file.sha256 is not None:
        return sha256_of(destination) == remote_file.sha256
    return git_blob_sha1_of(destination) == remote_file.git_blob_sha1
