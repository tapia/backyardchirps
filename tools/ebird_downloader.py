import argparse
import os
import sys
from pathlib import Path
from typing import Any

import django
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent

# A standalone script rather than a management command, because it needs an eBird key and
# is never run on a station. So it configures Django itself, and has to do it before
# importing anything from backyardchirps: those modules read settings as they load.
sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backyardchirps.settings")
os.environ.setdefault("SECRET_KEY", "not-used-by-this-tool")
django.setup()

from django.conf import settings

from backyardchirps.features.species.maintenance import geomodel_is_available
from backyardchirps.features.species.maintenance import plausible_species_names
from backyardchirps.features.species.taxonomy import taxonomy


class EbirdDownloader:
    BASE = "https://st-download.ebird.org/v1"

    def __init__(self, access_key: str, version: int = 2023):
        self.access_key = access_key
        self.version = version

    def download_species(
        self,
        species_code: str,
        output_dir: Path,
        product: str,
    ) -> None:
        species_dir = output_dir / species_code
        species_dir.mkdir(parents=True, exist_ok=True)

        objects = self._list_objects(species_code)

        wanted = [obj for obj in objects if self._is_wanted(obj, product)]

        for obj in wanted:
            filename = species_dir / Path(obj).name

            if filename.exists():
                continue

            url = f"{self.BASE}/fetch?objKey={obj}&key={self.access_key}"

            print("Downloading", filename.name)

            with requests.get(url, stream=True) as r:
                r.raise_for_status()

                with open(filename, "wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        f.write(chunk)

    def _is_wanted(self, obj: str, product: str) -> bool:
        if product in obj:
            return True
        # Occurrence rasters need their band-dates.csv companion for the timeline.
        return product.startswith("occurrence") and obj.endswith("band-dates.csv")

    def _list_objects(self, species_code: str) -> Any:
        url = f"{self.BASE}/list-obj/{self.version}/{species_code}?key={self.access_key}"

        r = requests.get(url)
        r.raise_for_status()
        return r.json()


def species_codes_for(latitude: float, longitude: float) -> list[str]:
    """
    The eBird codes of every species plausible at these coordinates.

    Both halves are derived rather than stored: the species come from GeoModel, the same
    call a station uses to build its own list, and the codes come from the taxonomy. A
    species the taxonomy has no code for is skipped, since there is no raster to ask for.
    """
    scientific_names = plausible_species_names(latitude, longitude)
    codes = []
    without_code = []
    for scientific_name in scientific_names:
        code = taxonomy.get_ebird_code(scientific_name)
        if code:
            codes.append(code)
        else:
            without_code.append(scientific_name)

    print(f"{len(scientific_names)} species plausible here, {len(codes)} with an eBird code")
    if without_code:
        print(f"No eBird code, skipped: {', '.join(without_code)}")
    return codes


def main() -> None:
    """
    Download eBird Status & Trends rasters into the shared assets/ebird_occurrence
    directory, for every species plausible at the given coordinates.
    """
    parser = argparse.ArgumentParser(description="Download eBird rasters for the species plausible at a location.")
    parser.add_argument("--latitude", type=float, required=True, help="Latitude of the location.")
    parser.add_argument("--longitude", type=float, required=True, help="Longitude of the location.")
    # The available products and their file-name tokens are documented in the
    # ebirdst API vignette: https://ebird.github.io/ebirdst/articles/api.html
    parser.add_argument(
        "--product",
        default="occurrence_median_9km",
        help=(
            "eBird Status & Trends product token to download, for example "
            "occurrence_median_9km (the raster the seasonality timeline samples, "
            "default) or range_smooth_9km (range-map source). See "
            "https://ebird.github.io/ebirdst/articles/api.html for the full list."
        ),
    )
    arguments = parser.parse_args()

    access_key = os.environ.get("EBIRD_API_KEY")
    if not access_key:
        raise SystemExit("Set EBIRD_API_KEY to your eBird Status & Trends access key.")

    if not geomodel_is_available():
        raise SystemExit("GeoModel is not downloaded. Run: uv run python manage.py download_birdnet3_model")

    output_dir = Path(settings.EBIRD_DATA_DIR)
    print(f"Downloading into {output_dir}")

    species_codes = species_codes_for(arguments.latitude, arguments.longitude)

    downloader = EbirdDownloader(access_key)
    for species_code in species_codes:
        downloader.download_species(species_code, output_dir, arguments.product)


if __name__ == "__main__":
    main()
