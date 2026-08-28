from typing import Any

from django.db import migrations

_RENAMES = {
    "analysis_low_confidence": "analysis_min_confidence",
    "analysis_medium_confidence": "analysis_auto_confirm_confidence",
}


def name_the_thresholds_after_their_job(apps: Any, schema_editor: Any) -> None:
    """
    Move each stored threshold to its new key, keeping the value the station chose.

    "Low" and "medium" described where the numbers sat on a scale, back when there was a
    third one above them. What is left is one floor and one bar, and the names now say
    which is which.
    """
    AppSetting = apps.get_model("birds_recorder", "AppSetting")
    for old_key, new_key in _RENAMES.items():
        # A row under the new name should be impossible, but a half-applied migration is
        # not worth a crash on the next attempt: the old row is the one to keep.
        AppSetting.objects.filter(key=new_key).delete()
        AppSetting.objects.filter(key=old_key).update(key=new_key)


class Migration(migrations.Migration):
    dependencies = [
        ("birds_recorder", "0009_drop_the_display_only_threshold"),
    ]

    operations = [
        migrations.RunPython(name_the_thresholds_after_their_job, migrations.RunPython.noop),
    ]
