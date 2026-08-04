from backyardchirps.models.setting import AppSetting


def get_all(keys: list[str]) -> dict[str, str]:
    """
    Several settings in one query. A key with no row is left out of the result.
    """
    return {row.key: row.value for row in AppSetting.objects.filter(key__in=keys)}


def get(key: str, default: str | None = None) -> str | None:
    return AppSetting.get(key, default)


def set_value(key: str, value: str) -> None:
    AppSetting.set(key, value)
