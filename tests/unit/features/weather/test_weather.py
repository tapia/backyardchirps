import pytest

from backyardchirps.features.weather.logic import WeatherCondition
from backyardchirps.features.weather.logic import WeatherReading
from backyardchirps.features.weather.logic import _compass_from_degrees
from backyardchirps.features.weather.logic import _condition_from_weather_code
from backyardchirps.features.weather.logic import serialize_weather_reading


@pytest.mark.parametrize(
    ("code", "is_day", "expected"),
    [
        (0, True, WeatherCondition.CLEAR_DAY),
        (0, False, WeatherCondition.CLEAR_NIGHT),
        (1, True, WeatherCondition.CLOUDY),
        (2, True, WeatherCondition.CLOUDY),
        (3, True, WeatherCondition.CLOUDY),
        (45, True, WeatherCondition.FOG),
        (48, True, WeatherCondition.FOG),
        (61, True, WeatherCondition.RAIN),
        (80, True, WeatherCondition.RAIN),
        (71, True, WeatherCondition.SNOW),
        (86, True, WeatherCondition.SNOW),
        (95, True, WeatherCondition.THUNDERSTORM),
        (99, True, WeatherCondition.THUNDERSTORM),
        (100, True, WeatherCondition.UNKNOWN),
    ],
)
def test_condition_from_weather_code(code: int, is_day: bool, expected: WeatherCondition) -> None:
    assert _condition_from_weather_code(code, is_day) == expected


@pytest.mark.parametrize(
    ("degrees", "expected"),
    [
        (0, "N"),
        (45, "NE"),
        (90, "E"),
        (135, "SE"),
        (180, "S"),
        (225, "SW"),
        (270, "W"),
        (315, "NW"),
        (360, "N"),
        (359, "N"),
        (23, "NE"),
    ],
)
def test_compass_from_degrees(degrees: float, expected: str) -> None:
    assert _compass_from_degrees(degrees) == expected


def _reading() -> WeatherReading:
    return WeatherReading(
        temperature_celsius=20.0,
        condition=WeatherCondition.CLEAR_DAY,
        wind_speed_kmh=10.0,
        wind_direction_degrees=90.0,
    )


def test_serialize_weather_reading_celsius_and_kmh() -> None:
    result = serialize_weather_reading(_reading(), "celsius", "kmh")
    assert result["temperature"] == 20.0
    assert result["wind_speed"] == 10.0
    assert result["wind_direction_compass"] == "E"
    assert result["condition"] == "clear_day"


def test_serialize_weather_reading_converts_to_fahrenheit_and_mph() -> None:
    result = serialize_weather_reading(_reading(), "fahrenheit", "mph")
    assert result["temperature"] == 68.0
    assert result["wind_speed"] == 6.2
    assert result["temperature_unit"] == "fahrenheit"
    assert result["wind_speed_unit"] == "mph"


def test_serialize_weather_reading_none_is_null_shaped() -> None:
    result = serialize_weather_reading(None, "celsius", "kmh")
    assert result == {
        "temperature": None,
        "temperature_unit": "celsius",
        "condition": None,
        "wind_speed": None,
        "wind_speed_unit": "kmh",
        "wind_direction_degrees": None,
        "wind_direction_compass": None,
    }
