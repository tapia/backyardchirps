from pathlib import Path
from typing import TypedDict

from .django_settings import DATA_DIR
from .django_settings import MODELS_DIR
from .django_settings import RECORDER_STATE_DIR
from .django_settings import SPECIES_RUNTIME_DIR


class _RecordingSettings(TypedDict):
    sample_rate: int
    clip_duration: float
    step_duration: float
    detection_time_buffer_in_minutes: int


class _ClipsSettings(TypedDict):
    save_dir: Path


class _Birdnet3Settings(TypedDict):
    model_key: str
    target_sample_rate: int
    window_samples: int
    geomodel_threshold: float


class _ConsistencyFilterSettings(TypedDict):
    window_size: int
    min_detections: int
    bypass_confidence: float


class _ServerStatusThresholds(TypedDict):
    cpu_temperature: float
    cpu_load: float
    memory_percent: float
    sound_processing_queue_load: float


# The species plausible at this station, one scientific name per line. Narrows the search
# in the validation dialog and decides what counts as rare.
#
# The `update_species_data` command builds this file from the station's own coordinates,
# so there is no file until that has run. Nothing in the path names a region, because the
# list belongs to the point it was derived for and to nowhere else: two stations an hour
# apart get different files, and neither is "the Spanish list".
SPECIES_LIST_RUNTIME_FILE = SPECIES_RUNTIME_DIR / "species_birdnet.txt"

# Downloaded from Zenodo by the download_birdnet3_model command.
BIRDNET3_MODEL_FILE = MODELS_DIR / "model.onnx"
BIRDNET3_LABELS_FILE = MODELS_DIR / "labels.txt"

# BirdNET 3's location filter, a spatiotemporal occurrence model. The same command
# downloads it from Hugging Face.
GEOMODEL_MODEL_FILE = MODELS_DIR / "geomodel.onnx"
GEOMODEL_LABELS_FILE = MODELS_DIR / "geomodel_labels.txt"

# Read by both the settings parser and the analyzer factory. BirdNET 3 is the
# default, BirdNET 2 the fallback.
ACOUSTIC_MODELS: tuple[str, ...] = ("birdnet_2", "birdnet_3")

# ---------------------------------------------------------------------------
# Audio capture
# ---------------------------------------------------------------------------
# The microphone is missing here on purpose: it is an AppSetting, so the wizard can
# choose it. The recorder reads it at startup, like the other settings it caches.
RECORDING: _RecordingSettings = {
    "sample_rate": 48000,
    # Must stay 3.0: BirdNET was trained on 3-second windows.
    "clip_duration": 3.0,
    # Seconds of new audio between one clip and the next. When this is smaller than
    # clip_duration the clips overlap, so a call that falls between two of them is
    # still heard in full by at least one. At 1.5 the clips overlap by half. Set it
    # equal to clip_duration to turn the overlap off.
    "step_duration": 1.5,
    # Detections of the same species within the same time block are merged into
    # a single DB record (keeping the highest confidence). Must divide 60 evenly.
    "detection_time_buffer_in_minutes": 3,
}

# ---------------------------------------------------------------------------
# Consistency filter: drops one-off BirdNET hits, which are usually noise rather
# than a real call.
# ---------------------------------------------------------------------------
CONSISTENCY_FILTER: _ConsistencyFilterSettings = {
    # How many clips in a row the filter looks at.
    "window_size": 3,
    # How many of those clips must contain the species before it is accepted.
    # Set to 1 to turn the repetition check off.
    "min_detections": 2,
    # A hit this confident is accepted on its own, without waiting for repetition.
    # It catches the short calls (a House Sparrow chirp) that score very high but
    # only ever land in one clip.
    "bypass_confidence": 0.8,
}

# ---------------------------------------------------------------------------
# Where clips are written. The other clip settings live in AppSetting instead, so
# the settings UI can change them while the app runs.
# ---------------------------------------------------------------------------
CLIPS: _ClipsSettings = {
    "save_dir": DATA_DIR / "clips",
}

# ---------------------------------------------------------------------------
# BirdNET 3: a single large ONNX file covering birds worldwide, run straight
# through onnxruntime, so nothing here needs the birdnet package or TensorFlow. It
# narrows down to locally plausible species with GeoModel 3 rather than BirdNET 2's
# SpeciesList, which keeps the acoustic model and the range model on the same
# generation.
# ---------------------------------------------------------------------------
BIRDNET_3: _Birdnet3Settings = {
    # The ACTIVE_ACOUSTIC_MODEL value that selects this model. Which V3 model to run
    # is fixed in the analyzer, the same way BirdNET 2 pins its own.
    "model_key": "birdnet_3",
    # The model takes 3 seconds (window_samples) of mono audio at this rate.
    "target_sample_rate": 32000,
    "window_samples": 96000,
    # A species counts as present here once GeoModel gives it at least this
    # occurrence probability. BirdNET V3 publishes no recommended value, so this one
    # carries over from V2's location filter. Tune it by observation.
    "geomodel_threshold": 0.03,
}

# ---------------------------------------------------------------------------
# The admin dropdown shows a warning badge once a metric reaches its threshold.
# Disk usage is missing here on purpose: it follows CLIPS_MAX_DISK_USAGE_PERCENT.
#
# sound_processing_queue_load compares the time it takes to analyze one clip against
# the time left before the next clip arrives. At 100% the recorder can no longer
# keep up and its queue grows forever, so the threshold warns while there is still
# room to spare.
# ---------------------------------------------------------------------------
SERVER_STATUS_THRESHOLDS: _ServerStatusThresholds = {
    "cpu_temperature": 75.0,
    "cpu_load": 90.0,
    "memory_percent": 85.0,
    "sound_processing_queue_load": 80.0,
}

# ---------------------------------------------------------------------------
# How the two processes compare notes on the clip queue: run_recorder writes a small
# JSON snapshot after every clip, and the server-status endpoint reads it back. Once
# the file is older than the stale window the recorder is taken to be down, and the
# queue card reports itself unavailable.
# ---------------------------------------------------------------------------
RECORDER_HEARTBEAT_FILE = RECORDER_STATE_DIR / "recorder_heartbeat.json"
RECORDER_HEARTBEAT_STALE_SECONDS = 60
