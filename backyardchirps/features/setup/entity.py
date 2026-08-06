from dataclasses import dataclass
from enum import StrEnum


class SetupErrorCode(StrEnum):
    """
    What the setup workflow refuses to do, and why. The frontend turns each code into a
    translated message, so the text lives there, not here.
    """

    # The token presented does not match the one on disk.
    BAD_TOKEN = "bad_token"
    # A superuser already exists. The station belongs to somebody.
    ADMIN_EXISTS = "admin_exists"
    # There is no superuser yet, so setup cannot be finished.
    NO_ADMIN = "no_admin"
    # No username was given.
    USERNAME_REQUIRED = "username_required"
    # The password did not pass Django's validators. The messages saying why come with it.
    WEAK_PASSWORD = "weak_password"
    # The device index is not one of the input devices on this machine.
    UNKNOWN_DEVICE = "unknown_device"
    # The device is there but could not be opened, almost always because the recorder is
    # already holding it.
    DEVICE_BUSY = "device_busy"


@dataclass(frozen=True)
class SetupStatus:
    """
    Where the station is in setup. Nothing here is secret: the frontend router reads it
    before anyone has logged in, to decide whether to send a visitor to the wizard.

    is_complete is derived rather than stored. A station is set up once it has an owner
    and no longer has a token to hand itself to somebody else.
    """

    has_admin: bool
    has_token: bool

    @property
    def is_complete(self) -> bool:
        return self.has_admin and not self.has_token


@dataclass(frozen=True)
class AudioDevice:
    """
    One input device, as the wizard's picker shows it.
    """

    index: int
    name: str
    channels: int
    sample_rate: float
    is_default: bool


@dataclass(frozen=True)
class AudioLevel:
    """
    What a short listen on a device heard. Both are in the 0 to 1 range the samples come
    in, so the meter can show them without knowing anything about the device.

    peak drives the "is it clipping" reading and rms the "is anything there at all" one,
    which is why both are here: a loud click and a steady hum look the same in only one
    of them.
    """

    peak: float
    rms: float
