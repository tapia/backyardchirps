from datetime import datetime
from datetime import timezone
from zoneinfo import ZoneInfo

import pytest

from backyardchirps.features.weather.astronomy import AstronomyService
from backyardchirps.features.weather.astronomy import AstroTimes
from backyardchirps.features.weather.astronomy import serialize_astro_times

_MADRID = ZoneInfo("Europe/Madrid")


def test_parse_time_converts_local_to_utc() -> None:
    service = AstronomyService()
    # 06:30 in Madrid (CEST, UTC+2 in June) is 04:30 UTC.
    result = service._parse_time("2024-06-15", "06:30", _MADRID)
    assert result == datetime(2024, 6, 15, 4, 30, tzinfo=timezone.utc)


@pytest.mark.parametrize("time_value", ["", "-:-", None, 123, "not-a-time"])
def test_parse_time_rejects_invalid_values(time_value: object) -> None:
    service = AstronomyService()
    assert service._parse_time("2024-06-15", time_value, _MADRID) is None


def test_serialize_astro_times_flattens_events() -> None:
    sunrise = datetime(2024, 6, 15, 4, 30, tzinfo=timezone.utc)
    sunset = datetime(2024, 6, 15, 19, 45, tzinfo=timezone.utc)

    result = serialize_astro_times([AstroTimes(sunrise=sunrise, sunset=sunset)])

    assert result == {
        "events": [
            {"key": "sunrise", "time": sunrise.isoformat()},
            {"key": "sunset", "time": sunset.isoformat()},
        ]
    }


def test_serialize_astro_times_skips_none_entries_and_fields() -> None:
    sunrise = datetime(2024, 6, 15, 4, 30, tzinfo=timezone.utc)

    result = serialize_astro_times([None, AstroTimes(sunrise=sunrise, sunset=None)])

    assert result == {"events": [{"key": "sunrise", "time": sunrise.isoformat()}]}
