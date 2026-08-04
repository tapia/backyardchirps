from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from typing import Callable

from django.conf import settings

from backyardchirps.features.settings import queries as settings_repository


class SettingsKey(StrEnum):
    """
    Every setting the application supports. Each value is the key of its AppSetting row.
    """

    LOCATION_LAT = "location_lat"
    LOCATION_LON = "location_lon"
    ACTIVE_ACOUSTIC_MODEL = "active_acoustic_model"
    ANALYSIS_LOW_CONFIDENCE = "analysis_low_confidence"
    ANALYSIS_MEDIUM_CONFIDENCE = "analysis_medium_confidence"
    ANALYSIS_HIGH_CONFIDENCE = "analysis_high_confidence"
    CLIPS_MAX_DISK_USAGE_PERCENT = "clips_max_disk_usage_percent"
    NOTIFICATIONS_LANGUAGE = "notifications_language"
    NOTIFICATIONS_FIRST_TODAY_ENABLED = "notifications_first_today_enabled"
    NOTIFICATIONS_FIRST_TODAY_CONFIDENCE = "notifications_first_today_confidence"
    NOTIFICATIONS_RARE_ENABLED = "notifications_rare_enabled"
    NOTIFICATIONS_RARE_CONFIDENCE = "notifications_rare_confidence"
    NOTIFICATIONS_FIRST_YEAR_ENABLED = "notifications_first_year_enabled"
    NOTIFICATIONS_FIRST_YEAR_CONFIDENCE = "notifications_first_year_confidence"
    NOTIFICATIONS_LONG_ABSENT_ENABLED = "notifications_long_absent_enabled"
    NOTIFICATIONS_LONG_ABSENT_CONFIDENCE = "notifications_long_absent_confidence"
    NOTIFICATIONS_LONG_ABSENT_DAYS = "notifications_long_absent_days"
    NOTIFICATIONS_NEW_SPECIES_ENABLED = "notifications_new_species_enabled"
    NOTIFICATIONS_NEW_SPECIES_CONFIDENCE = "notifications_new_species_confidence"
    NOTIFICATIONS_PENDING_VALIDATION_ENABLED = "notifications_pending_validation_enabled"
    WEATHER_TEMPERATURE_UNIT = "weather_temperature_unit"
    WEATHER_WIND_SPEED_UNIT = "weather_wind_speed_unit"


class SettingsErrorCode(StrEnum):
    """
    The codes the parsers and Settings.set raise as ValueError messages. The frontend
    turns each one into a translated message, so the text lives there, not here.
    """

    # The value is not 'true', 'false', True, or False.
    BOOL = "invalid_boolean"
    # The value is not a decimal number in [0, 1].
    CONFIDENCE = "invalid_confidence"
    # The value is not a decimal number in [-90, 90].
    LAT = "invalid_latitude"
    # The value is not a decimal number in [-180, 180].
    LON = "invalid_longitude"
    # The value is not one of the supported language codes ('en', 'es').
    LANGUAGE = "invalid_language"
    # The value is not a whole number in [1, 365].
    DAYS = "invalid_days"
    # The value is not a whole number in [1, 99].
    PERCENTAGE = "invalid_percentage"
    # The key is not present in DEFAULTS.
    UNKNOWN = "unknown_setting"
    # The value is not 'celsius' or 'fahrenheit'.
    TEMPERATURE_UNIT = "invalid_temperature_unit"
    # The value is not 'kmh' or 'mph'.
    WIND_SPEED_UNIT = "invalid_wind_speed_unit"
    # The value is not one of the supported acoustic models.
    ACOUSTIC_MODEL = "invalid_acoustic_model"


@dataclass(frozen=True)
class SettingDefinition[T]:
    """
    The default value of one setting, and the parser that validates it.
    """

    default: T
    parser: Callable[[Any], T]


_SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"en", "es"})
_SUPPORTED_TEMPERATURE_UNITS: frozenset[str] = frozenset({"celsius", "fahrenheit"})
_SUPPORTED_WIND_SPEED_UNITS: frozenset[str] = frozenset({"kmh", "mph"})


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    raise ValueError(SettingsErrorCode.BOOL)


def parse_confidence(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(SettingsErrorCode.CONFIDENCE) from None
    if not 0 <= parsed <= 1:
        raise ValueError(SettingsErrorCode.CONFIDENCE)
    return parsed


def parse_lat(value: Any) -> float | None:
    """
    An empty value gives None, which is how "no location configured" is stored.
    """
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(SettingsErrorCode.LAT) from None
    if not -90 <= parsed <= 90:
        raise ValueError(SettingsErrorCode.LAT)
    return parsed


def parse_lon(value: Any) -> float | None:
    """
    An empty value gives None, which is how "no location configured" is stored.
    """
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(SettingsErrorCode.LON) from None
    if not -180 <= parsed <= 180:
        raise ValueError(SettingsErrorCode.LON)
    return parsed


def parse_language(value: Any) -> str:
    if isinstance(value, str) and value.lower() in _SUPPORTED_LANGUAGES:
        return value.lower()
    raise ValueError(SettingsErrorCode.LANGUAGE)


def parse_temperature_unit(value: Any) -> str:
    if isinstance(value, str) and value.lower() in _SUPPORTED_TEMPERATURE_UNITS:
        return value.lower()
    raise ValueError(SettingsErrorCode.TEMPERATURE_UNIT)


def parse_wind_speed_unit(value: Any) -> str:
    if isinstance(value, str) and value.lower() in _SUPPORTED_WIND_SPEED_UNITS:
        return value.lower()
    raise ValueError(SettingsErrorCode.WIND_SPEED_UNIT)


def parse_acoustic_model(value: Any) -> str:
    if isinstance(value, str) and value in settings.ACOUSTIC_MODELS:
        return value
    raise ValueError(SettingsErrorCode.ACOUSTIC_MODEL)


def parse_days(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(SettingsErrorCode.DAYS) from None
    if not 1 <= parsed <= 365:
        raise ValueError(SettingsErrorCode.DAYS)
    return parsed


def parse_percentage(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(SettingsErrorCode.PERCENTAGE) from None
    if not 1 <= parsed <= 99:
        raise ValueError(SettingsErrorCode.PERCENTAGE)
    return parsed


DEFAULTS: dict[SettingsKey, SettingDefinition[Any]] = {
    SettingsKey.LOCATION_LAT: SettingDefinition(default=None, parser=parse_lat),
    SettingsKey.LOCATION_LON: SettingDefinition(default=None, parser=parse_lon),
    SettingsKey.ACTIVE_ACOUSTIC_MODEL: SettingDefinition(default="birdnet_3", parser=parse_acoustic_model),
    SettingsKey.ANALYSIS_LOW_CONFIDENCE: SettingDefinition(default=0.4, parser=parse_confidence),
    SettingsKey.ANALYSIS_MEDIUM_CONFIDENCE: SettingDefinition(default=0.7, parser=parse_confidence),
    SettingsKey.ANALYSIS_HIGH_CONFIDENCE: SettingDefinition(default=0.9, parser=parse_confidence),
    SettingsKey.CLIPS_MAX_DISK_USAGE_PERCENT: SettingDefinition(default=85, parser=parse_percentage),
    SettingsKey.NOTIFICATIONS_LANGUAGE: SettingDefinition(default="es", parser=parse_language),
    SettingsKey.NOTIFICATIONS_FIRST_TODAY_ENABLED: SettingDefinition(default=True, parser=parse_bool),
    SettingsKey.NOTIFICATIONS_FIRST_TODAY_CONFIDENCE: SettingDefinition(default=0.9, parser=parse_confidence),
    SettingsKey.NOTIFICATIONS_RARE_ENABLED: SettingDefinition(default=True, parser=parse_bool),
    SettingsKey.NOTIFICATIONS_RARE_CONFIDENCE: SettingDefinition(default=0.75, parser=parse_confidence),
    SettingsKey.NOTIFICATIONS_FIRST_YEAR_ENABLED: SettingDefinition(default=True, parser=parse_bool),
    SettingsKey.NOTIFICATIONS_FIRST_YEAR_CONFIDENCE: SettingDefinition(default=0.9, parser=parse_confidence),
    SettingsKey.NOTIFICATIONS_LONG_ABSENT_ENABLED: SettingDefinition(default=True, parser=parse_bool),
    SettingsKey.NOTIFICATIONS_LONG_ABSENT_CONFIDENCE: SettingDefinition(default=0.9, parser=parse_confidence),
    SettingsKey.NOTIFICATIONS_LONG_ABSENT_DAYS: SettingDefinition(default=30, parser=parse_days),
    SettingsKey.NOTIFICATIONS_NEW_SPECIES_ENABLED: SettingDefinition(default=True, parser=parse_bool),
    SettingsKey.NOTIFICATIONS_NEW_SPECIES_CONFIDENCE: SettingDefinition(default=0.9, parser=parse_confidence),
    SettingsKey.NOTIFICATIONS_PENDING_VALIDATION_ENABLED: SettingDefinition(default=True, parser=parse_bool),
    SettingsKey.WEATHER_TEMPERATURE_UNIT: SettingDefinition(default="celsius", parser=parse_temperature_unit),
    SettingsKey.WEATHER_WIND_SPEED_UNIT: SettingDefinition(default="kmh", parser=parse_wind_speed_unit),
}


def _serialize(value: object) -> str:
    if value is None:
        return ""
    return str(value)


class Settings:
    """
    The way to read and write application settings. Nothing else should reach for
    AppSetting or settings_repository on its own.

    Reading a key with no row yet writes its default to the database, so every later
    read sees the same value.
    """

    @classmethod
    def get(cls, key: SettingsKey) -> Any:
        """
        On the first access the row does not exist yet, so it is created holding the
        default.
        """
        definition = DEFAULTS[key]
        stored = settings_repository.get(key)
        if stored is None:
            settings_repository.set_value(key, _serialize(definition.default))
            return definition.default
        return definition.parser(stored)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """
        Raises ValueError for an unknown key, and for a value the parser rejects.
        """
        try:
            settings_key = SettingsKey(key)
        except ValueError:
            raise ValueError(SettingsErrorCode.UNKNOWN) from None
        definition = DEFAULTS[settings_key]
        parsed = definition.parser(value)
        settings_repository.set_value(settings_key, _serialize(parsed))

    @classmethod
    def as_dict(cls) -> dict[str, Any]:
        """
        Every setting, keyed by name. Unlike get, a key with no row falls back to its
        default without writing anything.
        """
        stored = settings_repository.get_all(list(DEFAULTS.keys()))
        result: dict[str, Any] = {}
        for key, definition in DEFAULTS.items():
            raw = stored.get(key)
            result[key] = definition.parser(raw) if raw is not None else definition.default
        return result
