from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.middleware.csrf import get_token
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.setup import logic as setup_logic
from backyardchirps.features.setup.entity import SetupErrorCode
from backyardchirps.features.setup.logic import SetupError
from backyardchirps.features.setup.permissions import SESSION_FLAG
from backyardchirps.features.setup.permissions import IsSetupAuthorised
from backyardchirps.shared.http import request_body

# A caller who is not allowed to do a thing gets 403; one who asked for something the
# station cannot give gets 400. Only the busy microphone is neither, being a state that
# will pass on its own.
_STATUS_BY_CODE: dict[SetupErrorCode, int] = {
    SetupErrorCode.DEVICE_BUSY: 409,
}


@api_view(["GET"])
@permission_classes([AllowAny])
def setup_status(request: Request) -> Response:
    """
    Whether the wizard still has to run. Open to anyone, because the router asks before
    there is any account to authenticate against.
    """
    status = setup_logic.get_status()
    return Response(
        {
            "is_complete": status.is_complete,
            "has_admin": status.has_admin,
            "token_required": status.has_token,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def claim(request: Request) -> Response:
    """
    Trade the one-time token for a session allowed to run the wizard.
    """
    try:
        setup_logic.claim(str(request_body(request).get("token", "")))
    except SetupError as error:
        return _error_response(error)

    request.session[SESSION_FLAG] = True
    return Response({"csrf_token": get_token(request)})


@api_view(["POST"])
@permission_classes([IsSetupAuthorised])
def create_admin(request: Request) -> Response:
    """
    Create the station's first admin and log in as them.

    Logging in here is what lets the rest of the wizard reuse the ordinary settings API,
    which wants an admin. Django keeps the session data across the login, so the setup
    authorisation set by claim survives it.
    """
    body = request_body(request)
    username = str(body.get("username", ""))
    password = str(body.get("password", ""))

    try:
        setup_logic.create_admin_account(username, password)
    except SetupError as error:
        return _error_response(error)

    user = authenticate(request, username=username.strip(), password=password)
    if user is not None:
        login(request, user)

    return Response(
        {
            "is_authenticated": user is not None,
            "username": username.strip(),
            "is_staff": True,
            "csrf_token": get_token(request),
        }
    )


@api_view(["GET"])
@permission_classes([IsSetupAuthorised])
def audio_devices(request: Request) -> Response:
    """
    The microphones this machine can record from, and which one is selected.
    """
    return Response(
        {
            "devices": [
                {
                    "index": device.index,
                    "name": device.name,
                    "channels": device.channels,
                    "sample_rate": device.sample_rate,
                    "is_default": device.is_default,
                }
                for device in setup_logic.list_audio_devices()
            ],
            "selected": Settings.get(SettingsKey.AUDIO_DEVICE),
        }
    )


@api_view(["POST"])
@permission_classes([IsSetupAuthorised])
def choose_audio_device(request: Request) -> Response:
    """
    Record from this microphone. An empty device means the system default.
    """
    try:
        recorder_restarted = setup_logic.choose_audio_device(request_body(request).get("device"))
    except ValueError as error:
        return Response({"error": str(error)}, status=400)
    return Response({"recorder_restarted": recorder_restarted})


@api_view(["GET"])
@permission_classes([IsSetupAuthorised])
def audio_level(request: Request) -> Response:
    """
    Listen to a device for about a second and report what it heard, so the wizard can
    show a meter that moves when someone claps.
    """
    raw_device = request.GET.get("device")
    try:
        level = setup_logic.measure_audio_level(int(raw_device) if raw_device else None)
    except ValueError:
        return Response({"error": SetupErrorCode.UNKNOWN_DEVICE}, status=400)
    except SetupError as error:
        return _error_response(error)

    return Response({"peak": level.peak, "rms": level.rms})


@api_view(["POST"])
@permission_classes([IsSetupAuthorised])
def complete(request: Request) -> Response:
    """
    Finish setup, destroy the token, and start recording.
    """
    try:
        recorder_started = setup_logic.complete()
    except SetupError as error:
        return _error_response(error)

    request.session.pop(SESSION_FLAG, None)
    return Response({"recorder_started": recorder_started})


def _error_response(error: SetupError) -> Response:
    body: dict[str, object] = {"error": error.code.value}
    if error.messages:
        body["messages"] = error.messages
    return Response(body, status=_STATUS_BY_CODE.get(error.code, 400))
