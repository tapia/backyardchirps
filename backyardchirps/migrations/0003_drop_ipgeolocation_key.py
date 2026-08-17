from typing import Any

from django.db import migrations

_KEY = "ipgeolocation_api_key"


def drop_ipgeolocation_key(apps: Any, schema_editor: Any) -> None:
    """
    Remove the row for a setting that no longer exists.

    Sunrise and sunset are computed from the station's coordinates now, so nothing reads
    this key. Migration 0002 still copies it out of the environment, because it is the
    record of what that update did and rewriting it would not change any station that
    already ran it. This runs after it, so a station updating with the variable still in
    its .env ends with no row either way.
    """
    AppSetting = apps.get_model("birds_recorder", "AppSetting")
    AppSetting.objects.filter(key=_KEY).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("birds_recorder", "0002_credentials_from_environment"),
    ]

    operations = [
        migrations.RunPython(drop_ipgeolocation_key, migrations.RunPython.noop),
    ]
