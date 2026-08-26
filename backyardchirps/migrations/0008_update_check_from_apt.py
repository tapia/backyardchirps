from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    """
    Store the answer the update check found rather than a copy of what a server said.

    The manifest column held the JSON of the release manifest, which no longer exists: apt
    is what a station asks now, and what it gets back is a version, two pieces of metadata
    and apt's own verdict on whether that version is newer. Dropping the column loses the
    result of the last check on an existing station, which the next check replaces anyway.
    """

    dependencies = [
        ("birds_recorder", "0007_drop_active_acoustic_model"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="storedupdatecheck",
            name="manifest",
        ),
        migrations.AddField(
            model_name="storedupdatecheck",
            name="version",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="storedupdatecheck",
            name="released",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="storedupdatecheck",
            name="changelog_url",
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="storedupdatecheck",
            name="update_available",
            field=models.BooleanField(default=False),
        ),
    ]
