import logging
from typing import Any

from django.core.management.base import BaseCommand

from backyardchirps.features.updates import logic as updates_logic

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check whether a newer release has been published, and store the answer"

    def handle(self, *args: Any, **options: Any) -> None:
        result = updates_logic.check_for_update()
        if not result.succeeded:
            logger.warning("The check did not complete: %s", result.error)
            return
        if updates_logic.is_newer_than_current_version(result.version):
            logger.info("Update available: %s", result.version)
        else:
            logger.info("This station is up to date")
