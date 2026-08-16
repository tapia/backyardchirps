import logging
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from backyardchirps.features.recording import maintenance

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Download the BirdNET 3 acoustic model and labels from Zenodo and the GeoModel 3 location "
        "model from its GitHub release, skipping any file that is already current"
    )

    def handle(self, *args: Any, **options: Any) -> None:
        acoustic = maintenance.refresh_birdnet3_model(
            model_destination=Path(settings.BIRDNET3_MODEL_FILE),
            labels_destination=Path(settings.BIRDNET3_LABELS_FILE),
        )
        geomodel = maintenance.refresh_geomodel(
            model_destination=Path(settings.GEOMODEL_MODEL_FILE),
            labels_destination=Path(settings.GEOMODEL_LABELS_FILE),
        )
        written = acoustic + geomodel
        if written:
            logger.info("BirdNET 3 assets updated: %s", ", ".join(written))
        else:
            logger.info("BirdNET 3 assets already up to date")
