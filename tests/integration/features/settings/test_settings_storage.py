import pytest

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.models.setting import AppSetting

pytestmark = pytest.mark.django_db


def test_a_fresh_database_holds_no_settings() -> None:
    # Also the guard on the test environment: conftest blanks the credentials that
    # migration 0002 would otherwise copy out of the developer's .env.
    assert AppSetting.objects.count() == 0


def test_get_falls_back_to_the_default_without_writing_a_row() -> None:
    assert Settings.get(SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE) == 0.7

    # Reading must not write. A GET request that stores rows would surprise anyone adding
    # caching or a read-only mode, and the recorder reads settings on every clip.
    assert AppSetting.objects.count() == 0


def test_as_dict_falls_back_to_defaults_without_writing_rows() -> None:
    values = Settings.as_dict()

    assert values[SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE] == 0.7
    assert values[SettingsKey.LOCATION_LAT] is None
    assert AppSetting.objects.count() == 0


def test_set_writes_a_row_that_get_then_reads_back() -> None:
    Settings.set(SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE, "0.55")

    assert AppSetting.objects.count() == 1
    assert Settings.get(SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE) == 0.55
    assert Settings.as_dict()[SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE] == 0.55


def test_get_and_as_dict_agree_for_a_key_with_no_row() -> None:
    key = SettingsKey.NOTIFICATIONS_LONG_ABSENT_DAYS

    assert Settings.get(key) == Settings.as_dict()[key]
    assert AppSetting.objects.count() == 0
