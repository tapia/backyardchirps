from typing import Callable

import pytest

from backyardchirps.features.detections import maintenance as enforce_clip_disk_quota


@pytest.fixture
def usage_sequence(monkeypatch: pytest.MonkeyPatch) -> Callable[[list[float]], None]:
    """
    Make disk_usage.get_usage_percent return the given values in order.
    """

    def _install(values: list[float]) -> None:
        remaining = list(values)
        monkeypatch.setattr(
            enforce_clip_disk_quota.disk_usage,
            "get_usage_percent",
            lambda _path: remaining.pop(0) if remaining else values[-1],
        )

    return _install


@pytest.fixture(autouse=True)
def fixed_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    # Quota of 85%; keep the use case off the database.
    monkeypatch.setattr(enforce_clip_disk_quota.Settings, "get", lambda key: 85)


def test_deletes_until_usage_drops_below_quota(
    monkeypatch: pytest.MonkeyPatch, usage_sequence: Callable[[list[float]], None]
) -> None:
    # Over quota, then a batch is deleted, then under quota.
    usage_sequence([90, 80, 80])
    deleted_ids: list[int] = []
    cleared_ids: list[int] = []
    monkeypatch.setattr(
        enforce_clip_disk_quota.detection_queries,
        "get_oldest_clips",
        lambda limit: [{"id": 1, "clip_path": "/a.wav"}, {"id": 2, "clip_path": "/b.wav"}],
    )
    monkeypatch.setattr(enforce_clip_disk_quota.AudioClip, "delete_clip", lambda path: deleted_ids.append(path))
    monkeypatch.setattr(enforce_clip_disk_quota.detection_queries, "clear_clip_path", lambda pk: cleared_ids.append(pk))

    deleted_count = enforce_clip_disk_quota.enforce_quota()

    assert deleted_count == 2
    assert deleted_ids == ["/a.wav", "/b.wav"]
    assert cleared_ids == [1, 2]


def test_stops_when_no_candidates_remain(
    monkeypatch: pytest.MonkeyPatch, usage_sequence: Callable[[list[float]], None]
) -> None:
    # Perpetually over quota, but nothing left to delete: the loop must break.
    usage_sequence([90])
    monkeypatch.setattr(enforce_clip_disk_quota.detection_queries, "get_oldest_clips", lambda limit: [])

    def _unexpected_delete(path: str) -> None:
        raise AssertionError("should not delete when there are no candidates")

    monkeypatch.setattr(enforce_clip_disk_quota.AudioClip, "delete_clip", _unexpected_delete)

    assert enforce_clip_disk_quota.enforce_quota() == 0
