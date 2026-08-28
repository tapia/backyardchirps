from typing import Any

from django.db import migrations

_KEY = "analysis_high_confidence"


def drop_the_display_only_threshold(apps: Any, schema_editor: Any) -> None:
    """
    Remove the row for a setting that no longer exists.

    It never changed what was recorded or what went to the review queue. All it did was
    set the floor for the navbar's "High" filter, and that filter is gone.
    """
    AppSetting = apps.get_model("birds_recorder", "AppSetting")
    AppSetting.objects.filter(key=_KEY).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("birds_recorder", "0008_update_check_from_apt"),
    ]

    operations = [
        migrations.RunPython(drop_the_display_only_threshold, migrations.RunPython.noop),
    ]
