from typing import Any

from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.http import Http404
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import translation
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.setup import logic as setup_logic
from backyardchirps.features.setup.entity import SetupErrorCode
from backyardchirps.features.setup.entity import SetupStatus
from backyardchirps.features.setup.logic import SetupError
from backyardchirps.features.setup.permissions import SESSION_FLAG
from backyardchirps.features.setup.permissions import IsSetupAuthorised

# The wizard in order. Which step a visitor is on is a URL, and moving on is a POST
# followed by a redirect, so reloading repeats nothing and a dropped connection costs at
# most the step being filled in. Nothing about the flow lives in a browser.
STEPS = ("language", "admin", "location", "microphone", "detection", "notifications", "done")

# What each step writes, by the names the settings API already uses. Both ends therefore
# agree on field names and validation, because both finish at Settings.set.
FIELDS_BY_STEP: dict[str, tuple[SettingsKey, ...]] = {
    "location": (SettingsKey.LOCATION_LAT, SettingsKey.LOCATION_LON),
    "detection": (
        SettingsKey.ANALYSIS_LOW_CONFIDENCE,
        SettingsKey.ANALYSIS_MEDIUM_CONFIDENCE,
        SettingsKey.ANALYSIS_HIGH_CONFIDENCE,
    ),
    "microphone": (SettingsKey.AUDIO_DEVICE,),
    "notifications": (
        SettingsKey.NOTIFICATIONS_LANGUAGE,
        SettingsKey.TELEGRAM_TOKEN,
        SettingsKey.TELEGRAM_CHAT_ID,
        SettingsKey.XENO_CANTO_API_KEY,
        SettingsKey.IPGEOLOCATION_API_KEY,
    ),
}

# The wizard's own language, chosen on the first step. Held in the session rather than
# saved, because it decides what this visitor reads now and nothing else: the site's
# language and the notification language are separate settings.
SESSION_LANGUAGE = "setup_language"

LANGUAGE_OPTIONS = (("en", "English"), ("es", "Espanol"))


def wizard(request: HttpRequest) -> HttpResponse:
    """
    Send a visitor to the step they are on.

    The entry point for anyone who types /setup/, and where the SPA sends people while
    the station is unconfigured.
    """
    if setup_logic.get_status().is_complete and not _is_mid_wizard(request):
        return redirect("/")
    return redirect(f"/setup/{_current_step(request)}/")


def wizard_step(request: HttpRequest, step: str) -> HttpResponse:
    """
    One step of the wizard: render it, or take its answers and move on.

    A finished station has no wizard, so every step redirects to the site once setup is
    complete. That is also what stops a second visitor walking in behind the owner.
    """
    if step not in STEPS:
        raise Http404("No such setup step.")

    status = setup_logic.get_status()
    if status.is_complete and not _is_mid_wizard(request):
        return redirect("/")

    refused = _refuse_unauthorised(request, step, status)
    if refused is not None:
        return refused

    with translation.override(_language(request)):
        if request.method == "POST":
            return _handle_post(request, step, status)
        return _render_step(request, step, status, errors={})


def audio_level(request: HttpRequest) -> JsonResponse:
    """
    What the microphone heard over about a second, for the meter on the microphone step.

    The one part of the wizard a page reload cannot do, so it stays a JSON endpoint that
    a few lines of script poll.
    """
    if not _is_authorised(request):
        return JsonResponse({"error": "forbidden"}, status=403)

    raw_device = request.GET.get("device")
    try:
        level = setup_logic.measure_audio_level(int(raw_device) if raw_device else None)
    except ValueError:
        return JsonResponse({"error": SetupErrorCode.UNKNOWN_DEVICE.value}, status=400)
    except SetupError as error:
        return JsonResponse({"error": error.code.value}, status=409)

    return JsonResponse({"peak": level.peak, "rms": level.rms})


@api_view(["GET"])
@permission_classes([AllowAny])
def setup_status(request: Request) -> Response:
    """
    Whether the wizard still has to run. Open to anyone, because the SPA asks before
    there is any account to authenticate against, and sends visitors to /setup/ when the
    answer is no.
    """
    status = setup_logic.get_status()
    return Response(
        {
            "is_complete": status.is_complete,
            "has_admin": status.has_admin,
            "token_required": status.has_token,
        }
    )


@api_view(["GET"])
@permission_classes([IsSetupAuthorised])
def audio_devices(request: Request) -> Response:
    """
    The microphones this machine can record from, and which one is selected.

    Outlives the wizard: the settings page lists the same devices when a station stops
    hearing anything.
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


def _current_step(request: HttpRequest) -> str:
    """
    The step this visitor should be on.

    Held in the session so that closing the browser mid-wizard and coming back lands
    where it left off. A station that already has an owner has nothing to do on the
    account step, so a resumed setup starts after it.
    """
    remembered = request.session.get("setup_step")
    if remembered in STEPS:
        return str(remembered)
    if setup_logic.get_status().has_admin:
        return "location"
    return STEPS[0]


def _is_mid_wizard(request: HttpRequest) -> bool:
    """
    Whether this session is walking the wizard right now.

    Setup counts as complete once the station has an owner and no token, which is right
    for a visitor arriving at /setup/ and wrong for the person who created that owner one
    step ago. A machine with no token file, a checkout, becomes complete the moment the
    account step runs, so without this the wizard would end there: no coordinates, and
    never a Finish to start the recorder. Both facts read here belong to the session that
    claimed the station, so nobody else can walk in on a finished setup.
    """
    return request.session.get("setup_step") in STEPS and _is_authorised(request)


def _refuse_unauthorised(request: HttpRequest, step: str, status: SetupStatus) -> HttpResponse | None:
    """
    Everything past the account step writes settings, so it needs the token holder or the
    owner. The first two steps are open, since choosing a language and presenting the
    token are what a visitor does before they are anybody.
    """
    if step in ("language", "admin"):
        return None
    if _is_authorised(request):
        return None
    return redirect("/setup/admin/")


def _is_authorised(request: HttpRequest) -> bool:
    """
    Either this session presented the token, or it belongs to the owner. The same two
    facts IsSetupAuthorised checks for the endpoints the SPA still calls, asked of a
    plain Django request.
    """
    if request.session.get(SESSION_FLAG) is True:
        return True
    return bool(request.user.is_authenticated and request.user.is_staff)


def _handle_post(request: HttpRequest, step: str, status: SetupStatus) -> HttpResponse:
    """
    Take a step's answers. On success the browser is redirected to the next step, so the
    back button and a reload both behave.
    """
    if step == "language":
        request.session[SESSION_LANGUAGE] = _chosen_language(request)
        return _advance(request, step)

    if step == "admin":
        error = _claim_or_sign_in(request, status)
        if error is not None:
            return _render_step(request, step, status, errors={"admin": error})
        return _advance(request, step)

    if step == "done":
        try:
            recorder_started = setup_logic.complete()
        except SetupError as error:
            return _render_step(request, step, status, errors={"done": error.code.value})
        request.session.pop(SESSION_FLAG, None)
        request.session.pop("setup_step", None)
        if recorder_started:
            return redirect("/")
        # Setup is finished either way, so there is nothing to retry and nowhere to send
        # them back to. Staying on this page is the only chance to say that the one thing
        # the station exists to do did not start.
        return _render_step(request, step, status, errors={"recorder": "not_started"})

    errors = _save_settings(request, step)
    if errors:
        return _render_step(request, step, status, errors=errors)
    return _advance(request, step)


def _claim_or_sign_in(request: HttpRequest, status: SetupStatus) -> str | None:
    """
    The account step, which does one of two things.

    A station with no owner trades the token for the first admin. A station that has one
    already, which is what an interrupted setup leaves behind, asks that owner to sign in
    instead. Creating a second admin is refused either way, so without this the only way
    back into an unfinished wizard would be the command line.
    """
    username = request.POST.get("username", "")
    password = request.POST.get("password", "")

    if status.has_admin:
        user = authenticate(request, username=username.strip(), password=password)
        if user is None or not user.is_staff:
            return SetupErrorCode.ADMIN_EXISTS.value
        login(request, user)
        return None

    try:
        setup_logic.claim(request.POST.get("token", ""))
        setup_logic.create_admin_account(username, password)
    except SetupError as error:
        return error.code.value

    request.session[SESSION_FLAG] = True
    # Logging in cycles the session key, and Django carries the session data across, so
    # the authorisation set just above survives it.
    user = authenticate(request, username=username.strip(), password=password)
    if user is not None:
        login(request, user)
    return None


def _save_settings(request: HttpRequest, step: str) -> dict[str, str]:
    """
    Write this step's fields, reporting a bad value against the field it came from.

    Empty is left alone rather than written, so a step whose fields are all optional can
    be walked past without clearing what a previous run put there.
    """
    errors: dict[str, str] = {}
    for key in FIELDS_BY_STEP.get(step, ()):
        if key not in request.POST:
            continue
        value = request.POST[key].strip()
        try:
            Settings.set(key, value)
        except ValueError as exc:
            errors[key] = str(exc)
    return errors


def _advance(request: HttpRequest, step: str) -> HttpResponse:
    """
    Remember the step reached and send the browser to the next one.
    """
    next_step = STEPS[STEPS.index(step) + 1]
    request.session["setup_step"] = next_step
    return redirect(f"/setup/{next_step}/")


def _render_step(request: HttpRequest, step: str, status: SetupStatus, errors: dict[str, str]) -> HttpResponse:
    """
    Draw one step, with whatever is already saved filled in.
    """
    step_index = STEPS.index(step)
    context: dict[str, Any] = {
        "step": step,
        "step_number": step_index + 1,
        "step_total": len(STEPS),
        "progress_percent": round((step_index + 1) / len(STEPS) * 100),
        # Never back into the account step. The account exists by then, so the form there
        # could only ask the owner to sign in again.
        "previous_step": STEPS[step_index - 1] if step_index > STEPS.index("admin") + 1 else None,
        "errors": errors,
        "settings": Settings.as_dict(),
        "token_required": status.has_token,
        "has_admin": status.has_admin,
        "language": _language(request),
        "language_options": LANGUAGE_OPTIONS,
    }
    if step == "microphone":
        context["devices"] = setup_logic.list_audio_devices()
    return render(request, f"setup/{step}.html", context)


def _language(request: HttpRequest) -> str:
    """
    The language this visitor picked on the first step, defaulting to the station's.
    """
    chosen = request.session.get(SESSION_LANGUAGE)
    return str(chosen) if chosen in dict(LANGUAGE_OPTIONS) else translation.get_language() or "en"


def _chosen_language(request: HttpRequest) -> str:
    submitted = request.POST.get("language", "")
    return submitted if submitted in dict(LANGUAGE_OPTIONS) else LANGUAGE_OPTIONS[0][0]
