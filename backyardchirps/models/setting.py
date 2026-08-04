from django.db import models


class AppSetting(models.Model):
    """
    Key/value store for the settings that can change while the app runs. Every value is a
    string here; the Settings class parses it into the right type.
    """

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()

    class Meta:
        verbose_name = "app setting"

    @classmethod
    def get(cls, key: str, default: str | None = None) -> str | None:
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key: str, value: str) -> None:
        cls.objects.update_or_create(key=key, defaults={"value": value})
