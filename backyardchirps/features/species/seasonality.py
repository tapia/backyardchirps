from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from django.conf import settings
from pyproj import Transformer

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.species.entity import Species


@dataclass
class SpeciesData:
    raster: rasterio.io.DatasetReader
    transformer: Transformer
    dates: pd.DataFrame


class SeasonalityPredictor:
    def __init__(self, root: str | Path = "data"):
        self.root = Path(root)
        self._cache: dict[str, SpeciesData] = {}

    def _load_species(self, species: str) -> SpeciesData:

        if species in self._cache:
            return self._cache[species]

        folder = self.root / species

        raster_path = next(folder.glob("*occurrence_median_9km*.tif"))
        dates_path = folder / "band-dates.csv"

        raster = rasterio.open(raster_path)

        transformer = Transformer.from_crs(
            "EPSG:4326",
            raster.crs,
            always_xy=True,
        )

        dates = pd.read_csv(
            dates_path,
            parse_dates=["date"],
        )

        data = SpeciesData(
            raster=raster,
            transformer=transformer,
            dates=dates,
        )

        self._cache[species] = data

        return data

    def get_seasonality_timeline(
        self,
        species: str,
        latitude: float,
        longitude: float,
    ) -> list[float | None]:

        data = self._load_species(species)

        x, y = data.transformer.transform(
            longitude,
            latitude,
        )

        bounds = data.raster.bounds

        if not (bounds.left <= x <= bounds.right and bounds.bottom <= y <= bounds.top):
            raise ValueError("Point lies outside raster extent.")

        values = next(data.raster.sample([(x, y)]))

        return [None if np.isnan(value) else float(value) for value in values]

    def get_band_dates(
        self,
        species: str,
    ) -> list[date]:
        """
        The calendar date of each weekly band, in band order, so that every value in the
        timeline can be placed at its point in the year.
        """

        data = self._load_species(species)

        return [timestamp.date() for timestamp in data.dates["date"]]

    def get_seasonality(
        self,
        species: str,
        latitude: float,
        longitude: float,
        when: date,
    ) -> float | None:

        data = self._load_species(species)

        timeline = self.get_seasonality_timeline(
            species,
            latitude,
            longitude,
        )

        target = pd.Timestamp(when)

        closest_index = int(data.dates["date"].sub(target).abs().idxmin())

        return timeline[closest_index]

    def close(self) -> None:
        for data in self._cache.values():
            data.raster.close()

        self._cache.clear()


_predictor: SeasonalityPredictor | None = None


def get_yearly_seasonality(
    species: Species,
) -> list[dict[str, str | float | None]] | None:
    """
    The weekly seasonality timeline for a species at the recorder's location. Each entry
    is {"date": ISO date string, "probability": float | None}, the probability being how
    often the species occurs there, from 0 to 1.

    Returns None whenever the data cannot be found: no eBird code, no raster file, no
    location configured, or a location the species has no data for.
    """

    ebird_code = species.ebird_code()
    if ebird_code is None:
        return None

    latitude = Settings.get(SettingsKey.LOCATION_LAT)
    longitude = Settings.get(SettingsKey.LOCATION_LON)
    if latitude is None or longitude is None:
        return None

    predictor = _get_predictor()

    try:
        probabilities = predictor.get_seasonality_timeline(ebird_code, latitude, longitude)
        band_dates = predictor.get_band_dates(ebird_code)
    except (StopIteration, ValueError):
        return None

    return [
        {"date": band_date.isoformat(), "probability": probability}
        for band_date, probability in zip(band_dates, probabilities, strict=True)
    ]


def _get_predictor() -> SeasonalityPredictor:
    global _predictor

    if _predictor is None:
        _predictor = SeasonalityPredictor(root=settings.EBIRD_DATA_DIR)

    return _predictor
