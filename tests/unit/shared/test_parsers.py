import pytest
from django.test import RequestFactory

from backyardchirps.features.detections.views import _parse_range
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.shared import http as utils
from backyardchirps.shared.http import parse_dt
from backyardchirps.shared.http import resolve_confidence_level

_FILE_SIZE = 1000


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (None, None),
        ("", None),
        ("bytes=0-499", (0, 499)),
        ("bytes=500-", (500, 999)),
        ("bytes=-500", (500, 999)),
        ("bytes=0-100000", (0, 999)),  # end clamped to file size
        ("bytes=-1500", (0, 999)),  # suffix longer than file starts at 0
        ("bytes=-0", None),  # zero-length suffix
        ("bytes=2000-3000", None),  # start past end of file
        ("bytes=500-400", None),  # start after end
        ("bytes=-", None),  # both ends empty
        ("bytes=abc", None),  # malformed
    ],
)
def test_parse_range(header: str | None, expected: tuple[int, int] | None) -> None:
    assert _parse_range(header, _FILE_SIZE) == expected


@pytest.mark.parametrize("value", [None, "", "not-a-date"])
def test_parse_dt_returns_none_for_missing_or_invalid(value: str | None) -> None:
    assert parse_dt(value) is None


def test_parse_dt_makes_naive_datetime_aware() -> None:
    result = parse_dt("2024-06-15T08:00:00")
    assert result is not None
    assert result.tzinfo is not None


def test_parse_dt_preserves_aware_datetime() -> None:
    result = parse_dt("2024-06-15T08:00:00+00:00")
    assert result is not None
    assert result.utcoffset() is not None


def test_resolve_confidence_level_low_returns_none() -> None:
    request = RequestFactory().get("/", {"min_confidence": "low"})
    assert resolve_confidence_level(request) is None


@pytest.mark.parametrize(
    ("raw", "expected_key"),
    [
        ("medium", SettingsKey.ANALYSIS_MEDIUM_CONFIDENCE),
        ("high", SettingsKey.ANALYSIS_HIGH_CONFIDENCE),
        (None, SettingsKey.ANALYSIS_HIGH_CONFIDENCE),  # default is high
        ("foo", SettingsKey.ANALYSIS_HIGH_CONFIDENCE),  # invalid falls back to high
    ],
)
def test_resolve_confidence_level_maps_to_setting_key(
    monkeypatch: pytest.MonkeyPatch, raw: str | None, expected_key: SettingsKey
) -> None:
    requested_keys: list[SettingsKey] = []

    def fake_get(key: SettingsKey) -> float:
        requested_keys.append(key)
        return 0.9

    monkeypatch.setattr(utils.Settings, "get", staticmethod(fake_get))

    params = {} if raw is None else {"min_confidence": raw}
    request = RequestFactory().get("/", params)

    assert resolve_confidence_level(request) == 0.9
    assert requested_keys == [expected_key]
