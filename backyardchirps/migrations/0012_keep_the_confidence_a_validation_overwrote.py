from typing import Any

from django.db import migrations


def restore_overwritten_confidence(apps: Any, schema_editor: Any) -> None:
    """
    Put back the score BirdNET gave to every detection a person validated.

    Confirming used to write 1.0 over the confidence and keep the real number in
    original_confidence. The site shows a validated mark instead of a percentage now, so
    the 1.0 buys nothing and costs the only record of what the model actually heard.

    Rows validated before original_confidence existed have nothing to put back and keep
    their 1.0. There is no way to tell those apart from a genuine 100%, and both mean the
    same thing on a row a person has already checked.
    """
    StoredDetection = apps.get_model("birds_recorder", "StoredDetection")
    for detection in StoredDetection.objects.filter(original_confidence__isnull=False).iterator():
        detection.confidence = detection.original_confidence
        detection.save(update_fields=["confidence"])


class Migration(migrations.Migration):
    dependencies = [
        ("birds_recorder", "0011_raise_a_floor_the_filter_used_to_cover"),
    ]

    operations = [
        migrations.RunPython(restore_overwritten_confidence, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="storeddetection",
            name="original_confidence",
        ),
    ]
