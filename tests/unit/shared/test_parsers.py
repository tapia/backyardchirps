import pytest

from backyardchirps.features.detections.views import _parse_range
from backyardchirps.shared.http import parse_dt

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
