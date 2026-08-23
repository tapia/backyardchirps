from typing import Any

from django.core.management.base import BaseCommand

from backyardchirps.shared.migrations import migrations_ahead_of_this_release


class Command(BaseCommand):
    help = "Print migrations the database has applied that this release does not ship"

    def handle(self, *args: Any, **options: Any) -> None:
        for migration in migrations_ahead_of_this_release():
            self.stdout.write(migration)
