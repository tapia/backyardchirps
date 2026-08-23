from typing import Any

from django.core.management.base import BaseCommand

from backyardchirps.features.updates import queries as updates_queries


class Command(BaseCommand):
    help = "Print the version an admin asked the station to install, if any"

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(updates_queries.requested_version())
