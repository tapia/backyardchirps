from typing import Any

from django.db import migrations

_KEY = "xeno_canto_api_key"


def drop_xeno_canto_key(apps: Any, schema_editor: Any) -> None:
    """
    Remove the row for a setting that no longer exists.

    Reference recordings come from the installed region pack now. The search that finds
    them is the part that needs a key, and it happens once while a pack is built, so no
    station holds one. Same shape as migration 0003: migration 0002 still copies the key
    out of the environment, being the record of what that update did, and this runs after
    it so a station updating with the variable still in its .env ends with no row.
    """
    AppSetting = apps.get_model("birds_recorder", "AppSetting")
    AppSetting.objects.filter(key=_KEY).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("birds_recorder", "0003_drop_ipgeolocation_key"),
    ]

    operations = [
        migrations.RunPython(drop_xeno_canto_key, migrations.RunPython.noop),
    ]
