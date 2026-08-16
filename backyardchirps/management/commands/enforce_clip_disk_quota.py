from typing import Any

from django.core.management.base import BaseCommand

from backyardchirps.features.detections import maintenance as enforce_clip_disk_quota


class Command(BaseCommand):
    help = "Delete the oldest saved clips if clip storage exceeds the configured disk quota"

    def handle(self, *args: Any, **options: Any) -> None:
        deleted = enforce_clip_disk_quota.enforce_quota()
        self.stdout.write(f"Deleted {deleted} clip(s) to satisfy disk quota.")
