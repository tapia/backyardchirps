import pytest

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.models.setting import AppSetting

pytestmark = pytest.mark.django_db

# Counts are compared against a baseline rather than against zero, because the
# credentials migration seeds a row for every credential the environment happens to set.


def test_get_falls_back_to_the_default_without_writing_a_row() -> None:
    key = SettingsKey.ANALYSIS_MEDIUM_CONFIDENCE
    assert not AppSetting.objects.filter(key=key).exists()
    row_count = AppSetting.objects.count()

    assert Settings.get(key) == 0.7

    # Reading must not write. A GET request that stores rows would surprise anyone adding
    # caching or a read-only mode, and the recorder reads settings on every clip.
    assert not AppSetting.objects.filter(key=key).exists()
    assert AppSetting.objects.count() == row_count


def test_as_dict_falls_back_to_defaults_without_writing_rows() -> None:
    row_count = AppSetting.objects.count()

    values = Settings.as_dict()

    assert values[SettingsKey.ANALYSIS_MEDIUM_CONFIDENCE] == 0.7
    assert values[SettingsKey.LOCATION_LAT] is None
    assert AppSetting.objects.count() == row_count


def test_set_writes_a_row_that_get_then_reads_back() -> None:
    key = SettingsKey.ANALYSIS_MEDIUM_CONFIDENCE
    row_count = AppSetting.objects.count()

    Settings.set(key, "0.55")

    assert AppSetting.objects.count() == row_count + 1
    assert Settings.get(key) == 0.55
    assert Settings.as_dict()[key] == 0.55


def test_get_and_as_dict_agree_for_a_key_with_no_row() -> None:
    key = SettingsKey.NOTIFICATIONS_LONG_ABSENT_DAYS
    row_count = AppSetting.objects.count()

    assert Settings.get(key) == Settings.as_dict()[key]
    assert AppSetting.objects.count() == row_count
