from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from backyardchirps.features.recording.audio import devices
from backyardchirps.features.setup import queries as setup_queries
from backyardchirps.features.setup import token_file
from backyardchirps.features.setup.entity import AudioDevice
from backyardchirps.features.setup.entity import AudioLevel
from backyardchirps.features.setup.entity import SetupErrorCode
from backyardchirps.features.setup.entity import SetupStatus
from backyardchirps.integrations.systemd import restart_unit

# The unit holding the microphone. Restarted after the device changes, since the recorder
# opens it once at startup and never looks again.
RECORDER_UNIT = "backyardchirps-recorder"


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


def measure_audio_level(device: int | None) -> AudioLevel:
    """
    Raises SetupError(DEVICE_BUSY) when the microphone is already taken, which is the
    normal state of a running station: the recorder holds it.
    """
    try:
        peak, rms = devices.measure_input_level(device)
    except devices.DeviceBusy as exc:
        raise SetupError(SetupErrorCode.DEVICE_BUSY, messages=[str(exc)]) from None
    return AudioLevel(peak=peak, rms=rms)


def complete() -> bool:
    """
    Finish setup: throw the token away, which is what stops the wizard opening again,
    then start recording. Returns whether the recorder started.

    Refused before there is an admin, since a station with no account and no token could
    never be configured at all.

    This is where a station begins listening. Until now it has been deliberately silent,
    because a recorder with no coordinates matches against every species on earth. The
    token goes first: the recorder has to see a finished setup to stay started across the
    next deploy.
    """
    if not setup_queries.superuser_exists():
        raise SetupError(SetupErrorCode.NO_ADMIN)
    token_file.delete()
    return restart_unit(RECORDER_UNIT)
