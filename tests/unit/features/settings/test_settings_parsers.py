from typing import Any

import pytest

from backyardchirps.features.settings.logic import SettingsErrorCode
from backyardchirps.features.settings.logic import parse_bool
from backyardchirps.features.settings.logic import parse_confidence
from backyardchirps.features.settings.logic import parse_days
from backyardchirps.features.settings.logic import parse_language
from backyardchirps.features.settings.logic import parse_lat
from backyardchirps.features.settings.logic import parse_lon
from backyardchirps.features.settings.logic import parse_percentage
from backyardchirps.features.settings.logic import parse_temperature_unit
from backyardchirps.features.settings.logic import parse_wind_speed_unit


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        ("true", True),
        ("TRUE", True),
        ("false", False),
    ],
)
def test_parse_bool_valid(value: Any, expected: bool) -> None:
    assert parse_bool(value) is expected


@pytest.mark.parametrize("value", ["yes", "1", 1, None])
def test_parse_bool_invalid(value: Any) -> None:
    with pytest.raises(ValueError, match=SettingsErrorCode.BOOL.value):
        parse_bool(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0.0),
        (1, 1.0),
        (0.5, 0.5),
        ("0.7", 0.7),
    ],
)
def test_parse_confidence_valid(value: Any, expected: float) -> None:
    assert parse_confidence(value) == expected


@pytest.mark.parametrize("value", [-0.1, 1.1, "abc", None])
def test_parse_confidence_invalid(value: Any) -> None:
    with pytest.raises(ValueError, match=SettingsErrorCode.CONFIDENCE.value):
        parse_confidence(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        (0, 0.0),
        (90, 90.0),
        (-90, -90.0),
        ("45.5", 45.5),
    ],
)
def test_parse_lat_valid(value: Any, expected: float | None) -> None:
    assert parse_lat(value) == expected


@pytest.mark.parametrize("value", [90.1, -91, "abc"])
def test_parse_lat_invalid(value: Any) -> None:
    with pytest.raises(ValueError, match=SettingsErrorCode.LAT.value):
        parse_lat(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("", None),
        (180, 180.0),
        (-180, -180.0),
        ("-73.9", -73.9),
    ],
)
def test_parse_lon_valid(value: Any, expected: float | None) -> None:
    assert parse_lon(value) == expected


@pytest.mark.parametrize("value", [180.1, -181, "abc"])
def test_parse_lon_invalid(value: Any) -> None:
    with pytest.raises(ValueError, match=SettingsErrorCode.LON.value):
        parse_lon(value)


@pytest.mark.parametrize(("value", "expected"), [("en", "en"), ("es", "es"), ("EN", "en")])
def test_parse_language_valid(value: Any, expected: str) -> None:
    assert parse_language(value) == expected


@pytest.mark.parametrize("value", ["fr", "", 123, None])
def test_parse_language_invalid(value: Any) -> None:
    with pytest.raises(ValueError, match=SettingsErrorCode.LANGUAGE.value):
        parse_language(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("celsius", "celsius"), ("fahrenheit", "fahrenheit"), ("CELSIUS", "celsius")],
)
def test_parse_temperature_unit_valid(value: Any, expected: str) -> None:
    assert parse_temperature_unit(value) == expected


@pytest.mark.parametrize("value", ["kelvin", "", None])
def test_parse_temperature_unit_invalid(value: Any) -> None:
    with pytest.raises(ValueError, match=SettingsErrorCode.TEMPERATURE_UNIT.value):
        parse_temperature_unit(value)


@pytest.mark.parametrize(("value", "expected"), [("kmh", "kmh"), ("mph", "mph"), ("MPH", "mph")])
def test_parse_wind_speed_unit_valid(value: Any, expected: str) -> None:
    assert parse_wind_speed_unit(value) == expected


@pytest.mark.parametrize("value", ["ms", "", None])
def test_parse_wind_speed_unit_invalid(value: Any) -> None:
    with pytest.raises(ValueError, match=SettingsErrorCode.WIND_SPEED_UNIT.value):
        parse_wind_speed_unit(value)


@pytest.mark.parametrize(("value", "expected"), [(1, 1), (365, 365), ("30", 30)])
def test_parse_days_valid(value: Any, expected: int) -> None:
    assert parse_days(value) == expected


@pytest.mark.parametrize("value", [0, 366, "abc", None])
def test_parse_days_invalid(value: Any) -> None:
    with pytest.raises(ValueError, match=SettingsErrorCode.DAYS.value):
        parse_days(value)


@pytest.mark.parametrize(("value", "expected"), [(1, 1), (99, 99), ("50", 50)])
def test_parse_percentage_valid(value: Any, expected: int) -> None:
    assert parse_percentage(value) == expected


@pytest.mark.parametrize("value", [0, 100, "abc", None])
def test_parse_percentage_invalid(value: Any) -> None:
    with pytest.raises(ValueError, match=SettingsErrorCode.PERCENTAGE.value):
        parse_percentage(value)
