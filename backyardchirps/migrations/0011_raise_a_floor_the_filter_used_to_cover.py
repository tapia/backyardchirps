from typing import Any

from django.db import migrations

_KEY = "analysis_min_confidence"

# What a station that never touched the setting now gets, and the lowest floor this
# migration will leave behind.
_DEFAULT = 0.75


def raise_a_floor_the_filter_used_to_cover(apps: Any, schema_editor: Any) -> None:
    """
    Bring a stored floor below the new default up to it.

    Until now a low floor was safe: everything BirdNET heard went through the consistency
    filter, which threw away anything that did not repeat or score very high. That filter
    no longer decides what to keep, so the floor is the only thing standing between the
    microphone and the review queue. A station carrying 0.4 forward would wake up to a
    queue several times its old size, from a change it did not ask for.

    Raising it changes a value the owner may have chosen, which is why it only ever moves
    up to the default and never past it. Anyone who wants to hear more can set it back,
    and now sees the queue that comes with it.
    """
    AppSetting = apps.get_model("birds_recorder", "AppSetting")
    floor = AppSetting.objects.filter(key=_KEY).first()
    if floor is None:
        return
    try:
        stored = float(floor.value)
    except ValueError:
        # Not a number we wrote. Settings falls back to the default when it cannot parse
        # a row, so leaving it alone changes nothing.
        return
    if stored >= _DEFAULT:
        return
    floor.value = str(_DEFAULT)
    floor.save(update_fields=["value"])


class Migration(migrations.Migration):
    dependencies = [
        ("birds_recorder", "0010_name_the_thresholds_after_their_job"),
    ]

    operations = [
        migrations.RunPython(raise_a_floor_the_filter_used_to_cover, migrations.RunPython.noop),
    ]
