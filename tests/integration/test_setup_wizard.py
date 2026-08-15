"""
The setup wizard, which is server-rendered: one URL per step, a POST to move on.

Most of these drive it the way a browser does, because the flow is the thing worth
testing. Which step a visitor is on is a URL and a session, never anything a client
remembers on its own, so a test that follows redirects is testing the real mechanism.
"""

from pathlib import Path
from typing import Any

import pytest
from django.test import Client
from rest_framework.test import APIClient

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.setup import logic as setup_logic
from backyardchirps.features.setup.entity import AudioDevice

pytestmark = pytest.mark.django_db

TOKEN = "6b1f0c3a9d7e4f2b8c5a1e0d3f7b9a2c"
GOOD_PASSWORD = "a-good-long-password"


@pytest.fixture
def token_file(settings: Any, tmp_path: Path) -> Path:
    """
    A station that has been installed but not yet claimed.
    """
    path = tmp_path / "setup-token"
    path.write_text(f"{TOKEN}\n")
    settings.SETUP_TOKEN_FILE = path
    return path


@pytest.fixture
def no_token_file(settings: Any, tmp_path: Path) -> Path:
    """
    A checkout, or a station whose wizard has already run.
    """
    path = tmp_path / "setup-token"
    settings.SETUP_TOKEN_FILE = path
    return path


@pytest.fixture(autouse=True)
def stub_devices(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    No test may reach for a real microphone: CI has none, and a developer machine has one
    that would be opened for a second in the middle of a test run. Autouse, because
    forgetting it in one test is enough to make the suite depend on the sound card.
    """
    monkeypatch.setattr(
        setup_logic,
        "list_audio_devices",
        lambda: [AudioDevice(index=1, name="USB mic", channels=1, sample_rate=48000.0, is_default=True)],
    )


@pytest.fixture
def restarts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """
    The units the code asked systemd to restart. Recording every call rather than only
    the last, because when the recorder starts is the point of several of these tests.
    """
    restarted: list[str] = []

    def _restart(unit: str) -> bool:
        restarted.append(unit)
        return True

    monkeypatch.setattr(setup_logic, "restart_unit", _restart)
    return restarted


@pytest.fixture
def claimed_client(client: Client, token_file: Path) -> Client:
    """
    A browser that has been through the account step, which is what every step after it
    needs. Goes through the real form rather than setting a session flag by hand.
    """
    client.post("/setup/admin/", {"token": TOKEN, "username": "owner", "password": GOOD_PASSWORD})
    return client


# --- where a visitor lands ---------------------------------------------------


def test_setup_starts_at_the_first_step(client: Client, token_file: Path) -> None:
    response = client.get("/setup/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/setup/language/"


def test_setup_sends_a_finished_station_to_the_site(
    client: Client, no_token_file: Path, django_user_model: Any
) -> None:
    django_user_model.objects.create_superuser(username="owner", password="pw")

    assert client.get("/setup/").headers["Location"] == "/"
    assert client.get("/setup/location/").headers["Location"] == "/"


def test_an_unknown_step_is_not_a_page(client: Client, token_file: Path) -> None:
    assert client.get("/setup/coordinates/").status_code == 404


# --- language ----------------------------------------------------------------


def test_language_step_moves_on_to_the_account(client: Client, token_file: Path) -> None:
    response = client.post("/setup/language/", {"language": "en"})

    assert response.headers["Location"] == "/setup/admin/"
    assert client.session["setup_language"] == "en"


# --- the account step --------------------------------------------------------


def test_account_step_asks_for_the_token_when_there_is_one(client: Client, token_file: Path) -> None:
    response = client.get("/setup/admin/")

    assert response.status_code == 200
    assert 'name="token"' in response.content.decode()


def test_account_step_creates_the_admin_and_moves_on(client: Client, token_file: Path, django_user_model: Any) -> None:
    response = client.post("/setup/admin/", {"token": TOKEN, "username": "owner", "password": GOOD_PASSWORD})

    assert response.headers["Location"] == "/setup/location/"
    assert django_user_model.objects.get(username="owner").is_superuser is True


def test_account_step_refuses_the_wrong_token(client: Client, token_file: Path, django_user_model: Any) -> None:
    response = client.post("/setup/admin/", {"token": "not-it", "username": "owner", "password": GOOD_PASSWORD})

    assert response.status_code == 200
    assert django_user_model.objects.filter(username="owner").exists() is False


def test_account_step_refuses_a_weak_password(client: Client, token_file: Path, django_user_model: Any) -> None:
    response = client.post("/setup/admin/", {"token": TOKEN, "username": "owner", "password": "pw"})

    assert response.status_code == 200
    assert django_user_model.objects.filter(username="owner").exists() is False


def test_the_account_step_leaves_a_session_that_can_reach_the_rest(claimed_client: Client) -> None:
    """
    Creating the account logs in, and Django cycles the session key when it does. The
    authorisation taken from the token has to survive that.
    """
    assert claimed_client.get("/setup/location/").status_code == 200


# --- resuming a wizard that was interrupted ----------------------------------


def test_a_station_with_an_owner_resumes_after_the_account_step(
    client: Client, token_file: Path, django_user_model: Any
) -> None:
    """
    What an install interrupted after the account step leaves behind. The wizard has to
    lead somewhere: creating a second admin is refused, so without this the only way back
    in would be the command line.
    """
    django_user_model.objects.create_superuser(username="owner", password=GOOD_PASSWORD)

    assert client.get("/setup/").headers["Location"] == "/setup/location/"


def test_the_owner_signs_in_to_carry_on(client: Client, token_file: Path, django_user_model: Any) -> None:
    django_user_model.objects.create_superuser(username="owner", password=GOOD_PASSWORD)

    response = client.post("/setup/admin/", {"username": "owner", "password": GOOD_PASSWORD})

    assert response.headers["Location"] == "/setup/location/"
    assert client.get("/setup/microphone/").status_code == 200


def test_a_stranger_cannot_sign_in_to_someone_elses_station(
    client: Client, token_file: Path, django_user_model: Any
) -> None:
    django_user_model.objects.create_superuser(username="owner", password=GOOD_PASSWORD)

    response = client.post("/setup/admin/", {"username": "owner", "password": "guessing"})

    assert response.status_code == 200
    assert client.get("/setup/location/").headers["Location"] == "/setup/admin/"


def test_the_steps_after_the_account_are_closed_to_a_visitor(client: Client, token_file: Path) -> None:
    assert client.get("/setup/location/").headers["Location"] == "/setup/admin/"
    assert client.get("/setup/done/").headers["Location"] == "/setup/admin/"


# --- the steps that write settings -------------------------------------------


def test_location_step_saves_the_coordinates(claimed_client: Client) -> None:
    response = claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})

    assert response.headers["Location"] == "/setup/microphone/"
    assert Settings.get(SettingsKey.LOCATION_LAT) == 40.4
    assert Settings.get(SettingsKey.LOCATION_LON) == -3.7


def test_location_step_keeps_a_bad_value_off_the_station(claimed_client: Client) -> None:
    response = claimed_client.post("/setup/location/", {"location_lat": "over there", "location_lon": "-3.7"})

    assert response.status_code == 200
    assert Settings.get(SettingsKey.LOCATION_LAT) is None


def test_microphone_step_saves_the_device(claimed_client: Client) -> None:
    response = claimed_client.post("/setup/microphone/", {"audio_device": "1"})

    assert response.headers["Location"] == "/setup/detection/"
    assert Settings.get(SettingsKey.AUDIO_DEVICE) == 1


def test_detection_step_saves_the_thresholds(claimed_client: Client) -> None:
    response = claimed_client.post(
        "/setup/detection/",
        {"analysis_low_confidence": "0.5", "analysis_medium_confidence": "0.7", "analysis_high_confidence": "0.95"},
    )

    assert response.headers["Location"] == "/setup/notifications/"
    assert Settings.get(SettingsKey.ANALYSIS_LOW_CONFIDENCE) == 0.5


def test_notifications_step_may_be_walked_past(claimed_client: Client) -> None:
    response = claimed_client.post("/setup/notifications/", {})

    assert response.headers["Location"] == "/setup/done/"


# --- finishing ---------------------------------------------------------------


def test_finishing_destroys_the_token_and_starts_recording(
    claimed_client: Client, token_file: Path, restarts: list[str]
) -> None:
    response = claimed_client.post("/setup/done/", {})

    assert response.headers["Location"] == "/"
    assert not token_file.exists()
    assert restarts == [setup_logic.RECORDER_UNIT]


def test_nothing_before_finishing_starts_the_recorder(claimed_client: Client, restarts: list[str]) -> None:
    """
    With no coordinates the analyzer matches against every species on earth, so an
    unconfigured station has to stay silent until the last step.
    """
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})
    claimed_client.post("/setup/microphone/", {"audio_device": "1"})

    assert restarts == []


def test_finishing_says_so_when_the_recorder_does_not_start(
    claimed_client: Client, token_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(setup_logic, "restart_unit", lambda unit: False)

    response = claimed_client.post("/setup/done/", {})

    assert response.status_code == 200
    assert not token_file.exists()


def test_the_wizard_cannot_be_run_twice(claimed_client: Client, token_file: Path, restarts: list[str]) -> None:
    """
    The whole point of the token: once the wizard has been through, a second visitor
    reaches nothing. A client of its own, since claimed_client is logged in as the admin
    it created and would be let through as staff.
    """
    claimed_client.post("/setup/done/", {})

    stranger = Client()

    assert stranger.get("/setup/").headers["Location"] == "/"
    assert stranger.get("/setup/admin/").headers["Location"] == "/"


# --- what the SPA still calls ------------------------------------------------


def test_status_is_open_to_anyone(api_client: APIClient, token_file: Path) -> None:
    response = api_client.get("/api/setup/status/")

    assert response.status_code == 200
    assert response.data == {"is_complete": False, "has_admin": False, "token_required": True}


def test_status_is_complete_once_the_wizard_has_run(
    api_client: APIClient, no_token_file: Path, django_user_model: Any
) -> None:
    django_user_model.objects.create_superuser(username="owner", password="pw")

    assert api_client.get("/api/setup/status/").data["is_complete"] is True


def test_audio_devices_needs_the_owner_or_the_token(api_client: APIClient, token_file: Path) -> None:
    assert api_client.get("/api/setup/audio-devices/").status_code == 403


def test_audio_devices_lists_inputs_for_an_admin(admin_client: APIClient, no_token_file: Path) -> None:
    response = admin_client.get("/api/setup/audio-devices/")

    assert response.status_code == 200
    assert response.data["devices"][0]["name"] == "USB mic"
