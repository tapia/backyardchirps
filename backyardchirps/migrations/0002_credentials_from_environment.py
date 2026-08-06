import os

from django.db import migrations

# The environment variable each credential used to live in, and the AppSetting key it
# lives in now. A station that set any of these in .env would otherwise lose them on
# the update, and notifications failing silently is not something anyone would notice.
_MOVED_CREDENTIALS: dict[str, str] = {
    "TELEGRAM_TOKEN": "telegram_token",
    "TELEGRAM_CHAT_ID": "telegram_chat_id",
    "XENO_CANTO_API_KEY": "xeno_canto_api_key",
    "IPGEOLOCATION_API_KEY": "ipgeolocation_api_key",
}


def copy_credentials_from_environment(apps, schema_editor):
    """
    Carry the credentials over from .env, which is still loaded at this point.

    An existing row wins, so re-running this after the wizard has been used cannot
    overwrite what the operator typed there.
    """
    AppSetting = apps.get_model("birds_recorder", "AppSetting")
    for variable, key in _MOVED_CREDENTIALS.items():
        value = os.environ.get(variable, "").strip()
        if not value:
            continue
        AppSetting.objects.get_or_create(key=key, defaults={"value": value})


def drop_credentials(apps, schema_editor):
    AppSetting = apps.get_model("birds_recorder", "AppSetting")
    AppSetting.objects.filter(key__in=_MOVED_CREDENTIALS.values()).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("birds_recorder", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(copy_credentials_from_environment, drop_credentials),
    ]
