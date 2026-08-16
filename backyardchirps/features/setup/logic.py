import logging
from collections.abc import Iterator
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from backyardchirps.features.recording.audio import devices
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.setup import queries as setup_queries
from backyardchirps.features.setup import token_file
from backyardchirps.features.setup.entity import AudioDevice
from backyardchirps.features.setup.entity import AudioLevel
from backyardchirps.features.setup.entity import SetupErrorCode
from backyardchirps.features.setup.entity import SetupStatus
from backyardchirps.features.species.maintenance import refresh_species_list
from backyardchirps.integrations.systemd import restart_unit

logger = logging.getLogger(__name__)

# The unit holding the microphone. Restarted after the device changes, since the recorder
# opens it once at startup and never looks again.
RECORDER_UNIT = "backyardchirps-recorder"

# How long one meter stream lasts before the browser opens the next one. A cap rather
# than an endless response, so a tab forgotten on the microphone step gives the device
# back instead of holding it all day.
_METER_STREAM_SECONDS = 300.0


class SetupError(Exception):
    """
    The setup workflow refusing to do something. `messages` carries Django's own reasons
    for rejecting a password, which are worth showing as they are.
    """

    def __init__(self, code: SetupErrorCode, messages: list[str] | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.messages = messages or []


def get_status() -> SetupStatus:
    """
    Whether the station has been claimed. Safe to answer to anyone: it says that setup is
    unfinished, never how to finish it.
    """
    return SetupStatus(has_admin=setup_queries.superuser_exists(), has_token=token_file.exists())


def claim(candidate_token: str) -> None:
    """
    Check the one-time token. Raises SetupError unless the caller may run the wizard.

    A station with no token file is either a fresh checkout or one whose install predates
    the wizard, so it is claimable by whoever asks first, exactly as it would be if the
    token were lying next to it. Once it has an owner that stops: an admin account is
    what the token would have created, so there is nothing left to claim.
    """
    if not token_file.exists():
        if setup_queries.superuser_exists():
            raise SetupError(SetupErrorCode.ADMIN_EXISTS)
        return
    if not token_file.matches(candidate_token):
        raise SetupError(SetupErrorCode.BAD_TOKEN)


def create_admin_account(username: str, password: str) -> None:
    """
    The station's first and only automatically created account. Refused once one exists,
    so a claimed station cannot be handed to a second person.
    """
    if setup_queries.superuser_exists():
        raise SetupError(SetupErrorCode.ADMIN_EXISTS)
    if not username.strip():
        raise SetupError(SetupErrorCode.USERNAME_REQUIRED)
    try:
        validate_password(password)
    except ValidationError as exc:
        raise SetupError(SetupErrorCode.WEAK_PASSWORD, messages=list(exc.messages)) from None
    setup_queries.create_superuser(username.strip(), password)


def list_audio_devices() -> list[AudioDevice]:
    return [
        AudioDevice(index=index, name=name, channels=channels, sample_rate=sample_rate, is_default=is_default)
        for index, name, channels, sample_rate, is_default in devices.list_input_devices()
    ]


def stream_audio_levels(device: int | None) -> Iterator[AudioLevel]:
    """
    What the microphone is hearing, ten readings a second, until the cap runs out.

    Raises SetupError(DEVICE_BUSY) when the microphone is already taken, which is the
    normal state of a running station: the recorder holds it.
    """
    try:
        for peak, rms in devices.stream_input_levels(device, seconds=_METER_STREAM_SECONDS):
            yield AudioLevel(peak=peak, rms=rms)
    except devices.DeviceBusy as exc:
        raise SetupError(SetupErrorCode.DEVICE_BUSY, messages=[str(exc)]) from None


def complete(answers: dict[str, Any]) -> bool:
    """
    Finish setup: save everything the wizard was told, throw the token away, which is
    what stops the wizard opening again, then start recording. Returns whether the
    recorder started.

    Refused before there is an admin, since a station with no account and no token could
    never be configured at all.

    The answers are written here rather than step by step, so a wizard nobody finished
    leaves the station exactly as it was. Each one was already checked by the step that
    asked for it, and every parser accepts what it returned, so Settings.set is only
    repeating work here, not deciding anything new.

    This is where a station begins listening. Until now it has been deliberately silent,
    because a recorder with no coordinates matches against every species on earth. The
    settings go in before the recorder starts, since it reads the coordinates once at
    startup, and the token goes before that: the recorder has to see a finished setup to
    stay started across the next deploy. The species list is built in the same gap, for
    the same reason, and cannot stop any of this: see _build_species_list.
    """
    if not setup_queries.superuser_exists():
        raise SetupError(SetupErrorCode.NO_ADMIN)
    for key, value in answers.items():
        Settings.set(key, value)
    _build_species_list()
    token_file.delete()
    return restart_unit(RECORDER_UNIT)


def _build_species_list() -> None:
    """
    Work out which species live here, now that there are coordinates to ask about.

    Without this a new station waits for the daily timer, so its first day, the one day
    its owner is certainly watching, is spent searching the whole taxonomy and calling
    nothing rare. Every one of those is a working state, which is why it went unnoticed
    for so long, but it is the worst day to be in it.

    It runs before the recorder starts, because the recorder reads the list once at
    startup. It never raises: a station that cannot build a list is in the state it was
    already in, and refusing to finish setup over it would be far worse than the problem.

    The taxonomy is deliberately left alone. Refreshing it needs the network and is slow,
    and the copy that ships with the release is exactly what a fresh station should use.
    The daily timer picks it up later.
    """
    latitude = Settings.get(SettingsKey.LOCATION_LAT)
    longitude = Settings.get(SettingsKey.LOCATION_LON)
    if latitude is None or longitude is None:
        logger.warning("Setup finished with no coordinates, so no species list was built")
        return
    try:
        refresh_species_list(latitude, longitude)
    except Exception:
        logger.exception("Could not build the species list while finishing setup")
