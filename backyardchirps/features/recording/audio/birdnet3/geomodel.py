import logging
from pathlib import Path
from typing import cast

import numpy as np
import onnxruntime as ort

from backyardchirps.features.species.entity import Species

logger = logging.getLogger(__name__)


class GeoModel:
    """
    Given a latitude, longitude and BirdNET 48-week index, returns the species
    plausible at that place and time. BirdNet3Analyzer uses it as its location filter,
    the job SpeciesList does for BirdNET 2.
    """

    def __init__(self, model_path: Path, labels_path: Path) -> None:
        self._session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        # The input and output tensor names are not documented, so read them from the
        # loaded model rather than hard-coding them.
        self._input_name: str = self._session.get_inputs()[0].name
        self._output_name: str = self._session.get_outputs()[0].name
        self._species_by_index: dict[int, Species] = self._load_labels(labels_path)

    def allowed_species(self, latitude: float, longitude: float, week_48: int, threshold: float) -> set[Species]:
        """
        The species whose occurrence probability at this location and week reaches
        threshold, resolved against the taxonomy.
        """
        scores = self._run(latitude, longitude, week_48)
        return {
            species
            for class_index, species in self._species_by_index.items()
            if float(scores[class_index]) >= threshold
        }

    def _run(self, latitude: float, longitude: float, week_48: int) -> np.ndarray:
        model_input = np.array([[latitude, longitude, week_48]], dtype=np.float32)
        outputs = self._session.run([self._output_name], {self._input_name: model_input})
        # The output has shape (1, num_classes); drop the batch dimension.
        return cast(np.ndarray, outputs[0][0])

    def _load_labels(self, labels_path: Path) -> dict[int, Species]:
        # Each row is "taxon_id\tscientific name\tcommon name". Non-bird rows, such as
        # mammals and insects, resolve to None and are dropped.
        species_by_index: dict[int, Species] = {}
        for class_index, raw_line in enumerate(labels_path.read_text().splitlines()):
            columns = raw_line.split("\t")
            if len(columns) < 2:
                continue
            species = Species.from_scientific_name(columns[1].strip())
            if species is not None:
                species_by_index[class_index] = species
        return species_by_index
