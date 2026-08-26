import logging
from typing import Any

from django.core.management.base import BaseCommand

from backyardchirps.features.updates import logic as updates_logic

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Store the answer the privileged update check wrote down"

    def handle(self, *args: Any, **options: Any) -> None:
        result = updates_logic.import_update_check()
        if not result.succeeded:
            logger.warning("The check did not complete: %s", result.error)
        elif result.update_available:
            logger.info("Update available: %s", result.version)
        else:
            logger.info("This station is up to date")
