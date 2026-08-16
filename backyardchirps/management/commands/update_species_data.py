import logging
from typing import Any

from django.core.management.base import BaseCommand

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.species import maintenance as update_species_data

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Update the taxonomy and the active location's species list from upstream sources"

    def handle(self, *args: Any, **options: Any) -> None:
        update_species_data.refresh_taxonomy()
        latitude = Settings.get(SettingsKey.LOCATION_LAT)
        longitude = Settings.get(SettingsKey.LOCATION_LON)
        # Falling back to 0.0 here would build a species list for the Atlantic off Africa
        # and hand it to search and the rare-species rule. Having no list at all is the
        # honest state, and the app already handles it.
        if latitude is None or longitude is None:
            logger.warning("No location is configured, so the species list was left alone")
            return
        update_species_data.refresh_species_list(latitude, longitude)
