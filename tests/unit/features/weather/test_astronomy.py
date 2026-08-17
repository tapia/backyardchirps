from datetime import date
from datetime import datetime
from datetime import timezone
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from astral import Observer
from astral.sun import sunrise
from astral.sun import sunset

from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.weather import astronomy
from backyardchirps.features.weather.astronomy import AstroTimes
from backyardchirps.features.weather.astronomy import _event_time
from backyardchirps.features.weather.astronomy import get_for_date
from backyardchirps.features.weather.astronomy import serialize_astro_times

_MADRID = ZoneInfo("Europe/Madrid")
_MADRID_OBSERVER = Observer(latitude=40.4168, longitude=-3.7038)
# Far enough north that the sun stays up all day in June and down all day in December.
_SVALBARD_OBSERVER = Observer(latitude=78.2232, longitude=15.6267)


def _stub_location(monkeypatch: pytest.MonkeyPatch, latitude: float | None, longitude: float | None) -> None:
    """
    Answer the two settings get_for_date reads without going near the database.
    """
    values = {SettingsKey.LOCATION_LAT: latitude, SettingsKey.LOCATION_LON: longitude}

    def fake_get(key: SettingsKey) -> Any:
        return values[key]

    monkeypatch.setattr(astronomy.Settings, "get", staticmethod(fake_get))


def test_event_time_reads_the_date_locally_and_answers_in_utc() -> None:
    # 15 June 2024 in Madrid: the sun rises at 06:44 local, which is 04:44 UTC.
    result = _event_time(sunrise, _MADRID_OBSERVER, date(2024, 6, 15), _MADRID)

    assert result is not None
    assert result.tzinfo == timezone.utc
    assert result.replace(second=0) == datetime(2024, 6, 15, 4, 44, tzinfo=timezone.utc)


def test_event_time_is_none_when_the_sun_never_sets() -> None:
    assert _event_time(sunrise, _SVALBARD_OBSERVER, date(2024, 6, 15), _MADRID) is None
    assert _event_time(sunset, _SVALBARD_OBSERVER, date(2024, 6, 15), _MADRID) is None


def test_get_for_date_computes_both_events(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_location(monkeypatch, 40.4168, -3.7038)

    result = get_for_date(date(2024, 6, 15))

    assert result is not None
    assert result.sunrise is not None
    assert result.sunset is not None
    assert result.sunrise < result.sunset


@pytest.mark.parametrize(("latitude", "longitude"), [(None, -3.7038), (40.4168, None), (None, None)])
def test_get_for_date_is_none_without_coordinates(
    monkeypatch: pytest.MonkeyPatch, latitude: float | None, longitude: float | None
) -> None:
    _stub_location(monkeypatch, latitude, longitude)

    assert get_for_date(date(2024, 6, 15)) is None


def test_serialize_astro_times_flattens_events() -> None:
    sunrise_at = datetime(2024, 6, 15, 4, 30, tzinfo=timezone.utc)
    sunset_at = datetime(2024, 6, 15, 19, 45, tzinfo=timezone.utc)

    result = serialize_astro_times([AstroTimes(sunrise=sunrise_at, sunset=sunset_at)])

    assert result == {
        "events": [
            {"key": "sunrise", "time": sunrise_at.isoformat()},
            {"key": "sunset", "time": sunset_at.isoformat()},
        ]
    }


def test_serialize_astro_times_skips_none_entries_and_fields() -> None:
    sunrise_at = datetime(2024, 6, 15, 4, 30, tzinfo=timezone.utc)

    result = serialize_astro_times([None, AstroTimes(sunrise=sunrise_at, sunset=None)])

    assert result == {"events": [{"key": "sunrise", "time": sunrise_at.isoformat()}]}
