from typing import Any

from django.db import migrations

_KEY = "active_acoustic_model"


def drop_active_acoustic_model(apps: Any, schema_editor: Any) -> None:
    """
    Remove the row for a setting that no longer exists.

    BirdNET 2 is gone, so BirdNET 3 is the only acoustic model and there is nothing to
    choose between. A station that had switched back to BirdNET 2 moves to BirdNET 3 on
    its next recorder restart.
    """
    AppSetting = apps.get_model("birds_recorder", "AppSetting")
    AppSetting.objects.filter(key=_KEY).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("birds_recorder", "0006_storedupdaterequest"),
    ]

    operations = [
        migrations.RunPython(drop_active_acoustic_model, migrations.RunPython.noop),
    ]
