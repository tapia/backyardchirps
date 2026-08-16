"""
The setup wizard, which is server-rendered: one URL per step, a POST to move on.

Most of these drive it the way a browser does, because the flow is the thing worth
testing. Which step a visitor is on is a URL and a session, never anything a client
remembers on its own, so a test that follows redirects is testing the real mechanism.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import requests
from django.test import Client
from rest_framework.test import APIClient

from backyardchirps.features.recording.audio import devices
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.setup import logic as setup_logic
from backyardchirps.features.setup.entity import AudioDevice
from backyardchirps.features.setup.views import SESSION_LANGUAGE
from backyardchirps.integrations import region_packs

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
    monkeypatch.setattr(devices, "stream_input_levels", lambda device, seconds: iter([]))


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


def test_a_station_with_no_token_finishes_the_wizard_it_started(
    client: Client, no_token_file: Path, restarts: list[str]
) -> None:
    """
    A checkout has no token, so it counts as set up the moment the account step gives it
    an owner. The session already walking the wizard still has to reach the end: that is
    where the coordinates are asked for and where the recorder is started.
    """
    client.post("/setup/admin/", {"username": "owner", "password": GOOD_PASSWORD})

    moved_on = client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})

    assert moved_on.headers["Location"] == "/setup/region-pack/"
    assert client.post("/setup/done/", {}).headers["Location"] == "/"
    assert Settings.get(SettingsKey.LOCATION_LAT) == 40.4
    assert restarts == [setup_logic.RECORDER_UNIT]
    # And the way back in closes behind it.
    assert client.get("/setup/location/").headers["Location"] == "/"


def test_an_unknown_step_is_not_a_page(client: Client, token_file: Path) -> None:
    assert client.get("/setup/coordinates/").status_code == 404


# --- language ----------------------------------------------------------------


def test_the_wizard_opens_in_english(client: Client, token_file: Path) -> None:
    """
    The station's own LANGUAGE_CODE is Spanish and the wizard does not follow it, since
    whoever is holding a freshly installed Pi has chosen nothing yet. Checked on the
    lang attribute rather than on any translated text, which would pass for the wrong
    reason on a checkout whose catalog has not been compiled.
    """
    page = client.get("/setup/language/").content.decode()

    assert '<html lang="en">' in page
    assert 'value="en" checked' in page
    assert 'value="es" checked' not in page


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


# --- the steps that answer settings -------------------------------------------
#
# Nothing here reaches the database. Each step checks what it was given and keeps it for
# the last step, so these tests read the answer back off the step rather than out of
# Settings, and the section below is where the saving is tested.


def test_location_step_takes_the_coordinates(claimed_client: Client) -> None:
    response = claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})

    assert response.headers["Location"] == "/setup/region-pack/"
    assert Settings.get(SettingsKey.LOCATION_LAT) is None


def test_a_step_comes_back_holding_what_it_was_told(claimed_client: Client) -> None:
    """
    The answers are in the session, not the database, so Back has to draw them from
    there or the wizard would forget everything the moment somebody looked twice.
    """
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})

    page = claimed_client.get("/setup/location/").content.decode()

    assert 'value="40.4"' in page
    assert 'value="-3.7"' in page


def test_location_step_refuses_a_bad_value_and_keeps_the_good_one(claimed_client: Client, restarts: list[str]) -> None:
    response = claimed_client.post("/setup/location/", {"location_lat": "over there", "location_lon": "-3.7"})

    assert response.status_code == 200

    claimed_client.post("/setup/done/", {})

    assert Settings.get(SettingsKey.LOCATION_LAT) is None
    assert Settings.get(SettingsKey.LOCATION_LON) == -3.7


def test_microphone_step_takes_the_device(claimed_client: Client, restarts: list[str]) -> None:
    response = claimed_client.post("/setup/microphone/", {"audio_device": "1"})

    assert response.headers["Location"] == "/setup/detection/"

    claimed_client.post("/setup/done/", {})

    assert Settings.get(SettingsKey.AUDIO_DEVICE) == 1


def test_detection_step_takes_the_thresholds(claimed_client: Client, restarts: list[str]) -> None:
    response = claimed_client.post(
        "/setup/detection/",
        {"analysis_low_confidence": "0.5", "analysis_medium_confidence": "0.7", "analysis_high_confidence": "0.95"},
    )

    assert response.headers["Location"] == "/setup/notifications/"

    claimed_client.post("/setup/done/", {})

    assert Settings.get(SettingsKey.ANALYSIS_LOW_CONFIDENCE) == 0.5


def test_a_spanish_wizard_draws_numbers_it_can_read_back(claimed_client: Client) -> None:
    """
    Spanish writes 0,7 for 0.7, and both these steps draw a number into a field that is
    posted straight back to float(). Localised, they would refuse a step the reader only
    pressed Next on.
    """
    session = claimed_client.session
    session[SESSION_LANGUAGE] = "es"
    session.save()

    thresholds = claimed_client.get("/setup/detection/").content.decode()
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})
    coordinates = claimed_client.get("/setup/location/").content.decode()

    assert 'value="0.7"' in thresholds
    assert 'value="40.4"' in coordinates
    assert "," not in _field_value(coordinates, "location_lat")


def _field_value(page: str, name: str) -> str:
    match = re.search(rf'name="{name}" value="([^"]*)"', page)
    assert match is not None, f"no {name} field in the page"
    return match.group(1)


def test_notifications_step_may_be_walked_past(claimed_client: Client) -> None:
    response = claimed_client.post("/setup/notifications/", {})

    assert response.headers["Location"] == "/setup/done/"


# --- finishing ---------------------------------------------------------------


def test_finishing_saves_everything_the_wizard_was_told(claimed_client: Client, restarts: list[str]) -> None:
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})
    claimed_client.post("/setup/microphone/", {"audio_device": "1"})
    claimed_client.post(
        "/setup/detection/",
        {"analysis_low_confidence": "0.5", "analysis_medium_confidence": "0.7", "analysis_high_confidence": "0.95"},
    )
    claimed_client.post("/setup/notifications/", {"telegram_token": "  12345:abc  "})

    claimed_client.post("/setup/done/", {})

    assert Settings.get(SettingsKey.LOCATION_LAT) == 40.4
    assert Settings.get(SettingsKey.LOCATION_LON) == -3.7
    assert Settings.get(SettingsKey.AUDIO_DEVICE) == 1
    assert Settings.get(SettingsKey.ANALYSIS_HIGH_CONFIDENCE) == 0.95
    assert Settings.get(SettingsKey.TELEGRAM_TOKEN) == "12345:abc"


def test_an_abandoned_wizard_leaves_the_station_as_it_was(claimed_client: Client) -> None:
    """
    The reason the answers wait: somebody who walks half the wizard and closes the
    browser, or who is only trying it out on a laptop, changes nothing.
    """
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})
    claimed_client.post("/setup/microphone/", {"audio_device": "1"})

    assert Settings.get(SettingsKey.LOCATION_LAT) is None
    assert Settings.get(SettingsKey.LOCATION_LON) is None
    assert Settings.get(SettingsKey.AUDIO_DEVICE) is None


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


# --- the level meter ---------------------------------------------------------


def test_the_meter_is_closed_to_a_stranger(client: Client, token_file: Path) -> None:
    assert client.get("/setup/audio-level/").status_code == 403


def test_the_meter_streams_a_reading_at_a_time(claimed_client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    One reading per event, so the bar can move as each arrives rather than when the
    response finishes. A response that ends is a response nginx is free to buffer.
    """
    monkeypatch.setattr(devices, "stream_input_levels", lambda device, seconds: iter([(0.5, 0.25), (0.1, 0.05)]))

    response = claimed_client.get("/setup/audio-level/?device=1")

    assert response["Content-Type"] == "text/event-stream"
    body = b"".join(response.streaming_content).decode()
    # Every stream ends sooner or later, so the browser has to be told how soon to open
    # the next one. Left to itself it waits three seconds, and the meter dies meanwhile.
    assert body.startswith("retry: ")
    assert _readings(body) == [{"peak": 0.5, "rms": 0.25}, {"peak": 0.1, "rms": 0.05}]


def test_a_busy_microphone_is_reported_inside_the_stream(
    claimed_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Not as a status code. The response has already started by the time anything opens the
    device, so the only place left to say so is the stream itself.
    """
    monkeypatch.setattr(devices, "stream_input_levels", _refuse_to_open)

    response = claimed_client.get("/setup/audio-level/?device=1")

    assert response.status_code == 200
    assert _readings(b"".join(response.streaming_content).decode()) == [{"error": "device_busy"}]


def _refuse_to_open(device: int | None, seconds: float) -> Iterator[tuple[float, float]]:
    raise devices.DeviceBusy("Error opening InputStream: Device unavailable")
    yield  # pragma: no cover


def _readings(body: str) -> list[Any]:
    """
    The JSON payload of every data event in a server-sent event stream.
    """
    return [json.loads(line[len("data: ") :]) for line in body.splitlines() if line.startswith("data: ")]


# --- the species list ---------------------------------------------------------


@pytest.fixture
def species_list_builds(monkeypatch: pytest.MonkeyPatch) -> list[tuple[float, float]]:
    """
    The coordinates the species list was built for, if it was built at all. The real one
    needs GeoModel, which no test machine has.
    """
    built: list[tuple[float, float]] = []
    monkeypatch.setattr(
        setup_logic,
        "refresh_species_list",
        lambda latitude, longitude: built.append((latitude, longitude)),
    )
    return built


def test_finishing_builds_the_species_list_for_the_coordinates_just_given(
    claimed_client: Client, restarts: list[str], species_list_builds: list[tuple[float, float]]
) -> None:
    """
    Finishing is the first moment a station knows where it is. Left to the daily timer,
    its first day is spent searching the whole taxonomy and calling nothing rare.
    """
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})

    claimed_client.post("/setup/done/", {})

    assert species_list_builds == [(40.4, -3.7)]


def test_the_species_list_is_built_before_the_recorder_starts(
    claimed_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    The recorder reads the list once at startup, so building it afterwards would leave
    the first run without one.
    """
    order: list[str] = []
    monkeypatch.setattr(setup_logic, "refresh_species_list", lambda latitude, longitude: order.append("species list"))
    monkeypatch.setattr(setup_logic, "restart_unit", lambda unit: order.append("recorder") or True)
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})

    claimed_client.post("/setup/done/", {})

    assert order == ["species list", "recorder"]


def test_setup_still_finishes_when_the_species_list_cannot_be_built(
    claimed_client: Client, token_file: Path, restarts: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A station that cannot build a list is in the state it was already in. Refusing to
    finish setup over it would strand its owner in the wizard for no gain.
    """

    def _explode(latitude: float, longitude: float) -> None:
        raise OSError("no room on the card")

    monkeypatch.setattr(setup_logic, "refresh_species_list", _explode)
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})

    response = claimed_client.post("/setup/done/", {})

    assert response.headers["Location"] == "/"
    assert not token_file.exists()
    assert restarts == [setup_logic.RECORDER_UNIT]


def test_no_coordinates_means_no_species_list(
    claimed_client: Client, restarts: list[str], species_list_builds: list[tuple[float, float]]
) -> None:
    """
    Building one for 0, 0 would describe the Atlantic off Africa and hand it to search
    and the rare-species rule. Having none is the honest state.
    """
    claimed_client.post("/setup/done/", {})

    assert species_list_builds == []
    assert restarts == [setup_logic.RECORDER_UNIT]


# --- the region pack step -----------------------------------------------------

IBERIA_ENTRY = {
    "id": "iberian-peninsula",
    "names": {"en": "Iberian Peninsula", "es": "Península ibérica"},
    "bbox": {"west": -10.8, "south": 34.2, "east": 5.4, "north": 44.9},
    "version": "2026-08-16",
    "species_count": 312,
    "url": "https://example.com/iberian-peninsula.tar.zst",
    "sha256": "abc",
    "size_bytes": 180_000_000,
}


@pytest.fixture
def region_packs_index(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """
    What the index offers. Replaces the empty one every integration test gets.
    """
    entries = [IBERIA_ENTRY]
    monkeypatch.setattr(region_packs, "fetch_index", lambda: entries)
    return entries


def test_the_region_pack_step_offers_the_pack_that_covers_the_station(
    claimed_client: Client, region_packs_index: list[dict[str, Any]]
) -> None:
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})

    page = claimed_client.get("/setup/region-pack/").content.decode()

    assert "Iberian Peninsula" in page
    assert "312" in page
    assert 'data-region-pack-id="iberian-peninsula"' in page


def test_the_region_pack_step_offers_the_nearest_when_none_covers_the_station(
    claimed_client: Client, region_packs_index: list[dict[str, Any]]
) -> None:
    """
    A miss says which region pack is nearest and how far, so somebody outside every box learns
    something rather than seeing an empty step.
    """
    claimed_client.post("/setup/location/", {"location_lat": "52.4", "location_lon": "4.9"})

    page = claimed_client.get("/setup/region-pack/").content.decode()

    assert "No region pack covers where you are" in page
    assert "Iberian Peninsula" in page


def test_the_region_pack_step_is_walked_past_when_the_index_cannot_be_reached(
    claimed_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    A station with no internet during setup is a working station. It gets no region pack and a
    step it can walk through, rather than a wizard it cannot finish.
    """

    def _no_internet() -> list[dict[str, Any]]:
        raise requests.ConnectionError("no route to host")

    monkeypatch.setattr(region_packs, "fetch_index", _no_internet)
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})

    page = claimed_client.get("/setup/region-pack/")

    assert page.status_code == 200
    assert "could not be reached" in page.content.decode()
    assert claimed_client.post("/setup/region-pack/", {}).headers["Location"] == "/setup/microphone/"


def test_the_region_pack_step_saves_nothing_by_itself(
    claimed_client: Client, region_packs_index: list[dict[str, Any]]
) -> None:
    """
    Like every other step. Installing a pack is a button on it, not the step moving on.
    """
    claimed_client.post("/setup/location/", {"location_lat": "40.4", "location_lon": "-3.7"})

    claimed_client.post("/setup/region-pack/", {})

    assert Settings.get(SettingsKey.REGION_PACK) == ""
