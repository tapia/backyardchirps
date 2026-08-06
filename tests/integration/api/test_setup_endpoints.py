from pathlib import Path
from typing import Any

import pytest
from rest_framework.test import APIClient

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.setup import logic as setup_logic
from backyardchirps.features.setup.entity import AudioDevice

pytestmark = pytest.mark.django_db

TOKEN = "6b1f0c3a9d7e4f2b8c5a1e0d3f7b9a2c"


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


@pytest.fixture
def claimed_client(api_client: APIClient, token_file: Path) -> APIClient:
    api_client.post("/api/setup/claim/", {"token": TOKEN}, format="json")
    return api_client


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


# --- status ------------------------------------------------------------------


def test_status_is_open_to_anyone(api_client: APIClient, token_file: Path) -> None:
    response = api_client.get("/api/setup/status/")

    assert response.status_code == 200
    assert response.data == {"is_complete": False, "has_admin": False, "token_required": True}


def test_status_is_complete_once_claimed_and_owned(
    api_client: APIClient, no_token_file: Path, django_user_model: Any
) -> None:
    django_user_model.objects.create_superuser(username="owner", password="pw")

    response = api_client.get("/api/setup/status/")

    assert response.data["is_complete"] is True


def test_status_is_incomplete_while_the_token_survives(
    api_client: APIClient, token_file: Path, django_user_model: Any
) -> None:
    """
    An admin exists but the wizard was never finished, so it must still open.
    """
    django_user_model.objects.create_superuser(username="owner", password="pw")

    response = api_client.get("/api/setup/status/")

    assert response.data["is_complete"] is False


# --- claim -------------------------------------------------------------------


def test_claim_with_the_right_token(api_client: APIClient, token_file: Path) -> None:
    response = api_client.post("/api/setup/claim/", {"token": TOKEN}, format="json")

    assert response.status_code == 200
    assert "csrf_token" in response.data


def test_claim_with_the_wrong_token(api_client: APIClient, token_file: Path) -> None:
    response = api_client.post("/api/setup/claim/", {"token": "not-it"}, format="json")

    assert response.status_code == 400
    assert response.data["error"] == "bad_token"


def test_claim_needs_no_token_on_an_unclaimed_station(api_client: APIClient, no_token_file: Path) -> None:
    """
    A fresh checkout has no token file. Nothing to present, and nothing to protect yet.
    """
    response = api_client.post("/api/setup/claim/", {}, format="json")

    assert response.status_code == 200


def test_claim_refused_once_the_station_has_an_owner(
    api_client: APIClient, no_token_file: Path, django_user_model: Any
) -> None:
    django_user_model.objects.create_superuser(username="owner", password="pw")

    response = api_client.post("/api/setup/claim/", {}, format="json")

    assert response.status_code == 400
    assert response.data["error"] == "admin_exists"


# --- admin -------------------------------------------------------------------


def test_create_admin_requires_a_claim(api_client: APIClient, token_file: Path) -> None:
    response = api_client.post(
        "/api/setup/admin/", {"username": "owner", "password": "a-good-long-password"}, format="json"
    )

    assert response.status_code == 403


def test_create_admin_makes_a_superuser_and_logs_in(claimed_client: APIClient, django_user_model: Any) -> None:
    response = claimed_client.post(
        "/api/setup/admin/", {"username": "owner", "password": "a-good-long-password"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["is_authenticated"] is True
    assert django_user_model.objects.get(username="owner").is_superuser is True


def test_create_admin_keeps_the_session_usable_afterwards(claimed_client: APIClient) -> None:
    """
    Logging in cycles the session key. The setup authorisation has to survive that, or
    the wizard locks itself out on its own second step.
    """
    claimed_client.post("/api/setup/admin/", {"username": "owner", "password": "a-good-long-password"}, format="json")

    response = claimed_client.get("/api/setup/audio-devices/")

    assert response.status_code == 200


def test_create_admin_rejects_a_weak_password(claimed_client: APIClient) -> None:
    response = claimed_client.post("/api/setup/admin/", {"username": "owner", "password": "pw"}, format="json")

    assert response.status_code == 400
    assert response.data["error"] == "weak_password"
    assert response.data["messages"]


def test_create_admin_refused_when_one_exists(claimed_client: APIClient, django_user_model: Any) -> None:
    django_user_model.objects.create_superuser(username="first", password="pw")

    response = claimed_client.post(
        "/api/setup/admin/", {"username": "second", "password": "a-good-long-password"}, format="json"
    )

    assert response.status_code == 400
    assert response.data["error"] == "admin_exists"


# --- audio -------------------------------------------------------------------


def test_audio_devices_lists_inputs(claimed_client: APIClient) -> None:
    response = claimed_client.get("/api/setup/audio-devices/")

    assert response.status_code == 200
    assert response.data["devices"][0]["name"] == "USB mic"
    assert response.data["selected"] is None


def test_choose_audio_device_saves_the_setting(claimed_client: APIClient, restarts: list[str]) -> None:
    response = claimed_client.post("/api/setup/audio-device/", {"device": 1}, format="json")

    assert response.status_code == 200
    assert Settings.get(SettingsKey.AUDIO_DEVICE) == 1


def test_choose_audio_device_leaves_the_recorder_stopped_during_setup(
    claimed_client: APIClient, restarts: list[str]
) -> None:
    """
    Restarting here would start an unconfigured station recording, and would take the
    microphone away from the level meter on the very next step of the wizard.
    """
    response = claimed_client.post("/api/setup/audio-device/", {"device": 1}, format="json")

    assert response.data["recorder_restarted"] is False
    assert restarts == []


def test_choose_audio_device_restarts_the_recorder_after_setup(
    admin_client: APIClient, no_token_file: Path, restarts: list[str]
) -> None:
    """
    The same endpoint from the settings page, on a station already past setup.
    """
    response = admin_client.post("/api/setup/audio-device/", {"device": 1}, format="json")

    assert response.data["recorder_restarted"] is True
    assert restarts == [setup_logic.RECORDER_UNIT]


def test_choose_audio_device_accepts_the_system_default(claimed_client: APIClient, restarts: list[str]) -> None:
    response = claimed_client.post("/api/setup/audio-device/", {"device": ""}, format="json")

    assert response.status_code == 200
    assert Settings.get(SettingsKey.AUDIO_DEVICE) is None


def test_choose_audio_device_rejects_nonsense(claimed_client: APIClient) -> None:
    response = claimed_client.post("/api/setup/audio-device/", {"device": "the usb one"}, format="json")

    assert response.status_code == 400


def test_audio_level_reports_what_it_heard(claimed_client: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(setup_logic.devices, "measure_input_level", lambda device: (0.5, 0.1))

    response = claimed_client.get("/api/setup/audio-level/?device=1")

    assert response.status_code == 200
    assert response.data == {"peak": 0.5, "rms": 0.1}


def test_audio_level_says_when_the_recorder_holds_the_microphone(
    claimed_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _busy(device: int | None) -> tuple[float, float]:
        raise setup_logic.devices.DeviceBusy("Device unavailable")

    monkeypatch.setattr(setup_logic.devices, "measure_input_level", _busy)

    response = claimed_client.get("/api/setup/audio-level/?device=1")

    assert response.status_code == 409
    assert response.data["error"] == "device_busy"


# --- complete ----------------------------------------------------------------


def test_complete_destroys_the_token_and_starts_recording(
    claimed_client: APIClient, token_file: Path, restarts: list[str]
) -> None:
    claimed_client.post("/api/setup/admin/", {"username": "owner", "password": "a-good-long-password"}, format="json")

    response = claimed_client.post("/api/setup/complete/", {}, format="json")

    assert response.status_code == 200
    assert response.data["recorder_started"] is True
    assert not token_file.exists()
    assert restarts == [setup_logic.RECORDER_UNIT]


def test_complete_is_where_a_station_starts_listening(
    claimed_client: APIClient, token_file: Path, restarts: list[str]
) -> None:
    """
    Nothing before this may start the recorder: with no coordinates the analyzer matches
    against every species on earth, so an unconfigured station has to stay silent.
    """
    claimed_client.post("/api/setup/admin/", {"username": "owner", "password": "a-good-long-password"}, format="json")
    claimed_client.post("/api/setup/audio-device/", {"device": 1}, format="json")

    assert restarts == []

    claimed_client.post("/api/setup/complete/", {}, format="json")

    assert restarts == [setup_logic.RECORDER_UNIT]


def test_complete_refused_before_there_is_an_admin(
    claimed_client: APIClient, token_file: Path, restarts: list[str]
) -> None:
    response = claimed_client.post("/api/setup/complete/", {}, format="json")

    assert response.status_code == 400
    assert response.data["error"] == "no_admin"
    assert token_file.exists()


def test_the_wizard_cannot_be_run_twice(claimed_client: APIClient, token_file: Path, restarts: list[str]) -> None:
    """
    The whole point of the token: once the wizard has been through, a second visitor
    reaches nothing. A client of its own, since claimed_client is now logged in as the
    admin it created and would be let through as staff.
    """
    claimed_client.post("/api/setup/admin/", {"username": "owner", "password": "a-good-long-password"}, format="json")
    claimed_client.post("/api/setup/complete/", {}, format="json")

    stranger = APIClient()

    assert stranger.post("/api/setup/claim/", {"token": TOKEN}, format="json").status_code == 400
    assert stranger.get("/api/setup/audio-devices/").status_code == 403
