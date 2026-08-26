import json
import logging
from collections.abc import Iterator
from typing import Any

import requests
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.http import Http404
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import JsonResponse
from django.http import StreamingHttpResponse
from django.http.response import HttpResponseBase
from django.shortcuts import redirect
from django.shortcuts import render
from django.utils import translation
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.features.region_packs import logic as region_packs_logic
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.setup import logic as setup_logic
from backyardchirps.features.setup.entity import SetupErrorCode
from backyardchirps.features.setup.entity import SetupStatus
from backyardchirps.features.setup.logic import SetupError
from backyardchirps.features.setup.permissions import SESSION_FLAG
from backyardchirps.features.setup.permissions import IsSetupAuthorised
from backyardchirps.integrations import region_packs

logger = logging.getLogger(__name__)

# The wizard in order. Which step a visitor is on is a URL, and moving on is a POST
# followed by a redirect, so reloading repeats nothing and a dropped connection costs at
# most the step being filled in. Nothing about the flow lives in a browser.
STEPS = ("language", "admin", "location", "region-pack", "microphone", "detection", "notifications", "done")

# How long the browser waits before opening the next meter stream, in milliseconds. Every
# stream ends sooner or later, so this is the width of the gap in a meter that is working
# normally, not an error path.
_METER_RECONNECT_MS = 500

# What each step answers, by the names the settings API already uses. Both ends therefore
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
    ),
}

# The confidences, which the detection step asks for as whole percentages. They are
# stored from 0 to 1, the scale BirdNET scores on, but that is not how anyone reads a
# confidence: the settings page and every badge on the site write it as a percentage.
PERCENTAGE_FIELDS: frozenset[SettingsKey] = frozenset(
    {
        SettingsKey.ANALYSIS_LOW_CONFIDENCE,
        SettingsKey.ANALYSIS_MEDIUM_CONFIDENCE,
        SettingsKey.ANALYSIS_HIGH_CONFIDENCE,
    }
)

# The wizard's own language, chosen on the first step. Held in the session rather than
# saved, because it decides what this visitor reads now and nothing else: the site's
# language and the notification language are separate settings.
SESSION_LANGUAGE = "setup_language"

# Where the answers wait until the last step saves them all at once. A wizard nobody
# finished then leaves the station exactly as it was, which is what the Finish button
# has always promised, and what lets the whole thing be walked through on a laptop
# without keeping anything.
SESSION_ANSWERS = "setup_answers"

LANGUAGE_OPTIONS = (("en", "English"), ("es", "Español"))

# What the wizard opens in, and what the first step has selected before anybody chooses.
# English rather than the station's own LANGUAGE_CODE, which is Spanish: whoever is holding
# a freshly installed Pi has not chosen anything yet, and English is the language the
# installer that sent them here speaks.
DEFAULT_LANGUAGE = LANGUAGE_OPTIONS[0][0]


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

    refused = _refuse_unauthorised(request, step)
    if refused is not None:
        return refused

    with translation.override(_language(request)):
        if request.method == "POST":
            return _handle_post(request, step, status)
        return _render_step(request, step, status, errors={})


def audio_level(request: HttpRequest) -> HttpResponseBase:
    """
    A live reading of what the microphone hears, for the meter on the microphone step.

    The one part of the wizard a page reload cannot do. It is a stream of server-sent
    events rather than something to poll: the device stays open for as long as the
    browser is listening, so nothing that happens in front of the microphone falls
    between two readings, and no two readings ever fight over the device.
    """
    if not _is_authorised(request):
        return JsonResponse({"error": "forbidden"}, status=403)

    raw_device = request.GET.get("device")
    try:
        device = int(raw_device) if raw_device else None
    except ValueError:
        return JsonResponse({"error": SetupErrorCode.UNKNOWN_DEVICE.value}, status=400)

    response = StreamingHttpResponse(_audio_level_events(device), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    # Tell nginx not to collect the readings into a buffer, which would deliver them in
    # bursts and make the bar jump. The packaged nginx site says the same thing, but a response
    # that asks for itself also works behind a proxy this project did not write.
    response["X-Accel-Buffering"] = "no"
    return response


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


def _audio_level_events(device: int | None) -> Iterator[str]:
    """
    The meter stream, as server-sent events.

    A device that will not open is reported inside the stream rather than as a status
    code. The response has already begun by the time anything reaches for the device, and
    opening it earlier, to find out in time to pick a status, would leave a device open
    that nothing closes if the browser never reads the answer.
    """
    yield f"retry: {_METER_RECONNECT_MS}\n\n"
    try:
        for level in setup_logic.stream_audio_levels(device):
            yield f"data: {json.dumps({'peak': level.peak, 'rms': level.rms})}\n\n"
    except SetupError as error:
        yield f"data: {json.dumps({'error': error.code.value})}\n\n"


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


def _refuse_unauthorised(request: HttpRequest, step: str) -> HttpResponse | None:
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
            recorder_started = setup_logic.complete(_answers(request))
        except SetupError as error:
            return _render_step(request, step, status, errors={"done": error.code.value})
        request.session.pop(SESSION_FLAG, None)
        request.session.pop(SESSION_ANSWERS, None)
        request.session.pop("setup_step", None)
        if recorder_started:
            return redirect("/")
        # Setup is finished either way, so there is nothing to retry and nowhere to send
        # them back to. Staying on this page is the only chance to say that the one thing
        # the station exists to do did not start.
        return _render_step(request, step, status, errors={"recorder": "not_started"})

    errors = _remember_answers(request, step)
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


def _remember_answers(request: HttpRequest, step: str) -> dict[str, str]:
    """
    Check this step's fields and keep them for the last step, reporting a bad value
    against the field it came from. Nothing reaches the database here.

    A field the step did not send is left alone rather than remembered, so a step whose
    fields are all optional can be walked past without clearing an earlier answer.
    """
    answers = _answers(request)
    errors: dict[str, str] = {}
    for key in FIELDS_BY_STEP.get(step, ()):
        if key not in request.POST:
            continue
        value = request.POST[key].strip()
        if key in PERCENTAGE_FIELDS:
            value = _confidence_from_percentage(value)
        try:
            answers[key] = Settings.parse(key, value)
        except ValueError as exc:
            errors[key] = str(exc)
    # Kept even when a sibling field was refused, so a step is never re-drawn asking
    # again for what was already right.
    request.session[SESSION_ANSWERS] = answers
    return errors


def _answers(request: HttpRequest) -> dict[str, Any]:
    """
    What the wizard has been told so far, ready to be saved. Values are what
    Settings.parse gave back, not what was typed, so a step re-drawing itself shows them
    the way the settings page would.
    """
    remembered = request.session.get(SESSION_ANSWERS)
    return dict(remembered) if isinstance(remembered, dict) else {}


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
        # What is saved, with what this run has been told on top of it, so Back shows
        # the answers rather than the station's old values.
        "settings": Settings.as_dict() | _answers(request),
        "token_required": status.has_token,
        "has_admin": status.has_admin,
        "language": _language(request),
        "language_options": LANGUAGE_OPTIONS,
    }
    if step == "detection":
        context["percentages"] = _percentages(context["settings"])
    if step == "microphone":
        context["devices"] = setup_logic.list_audio_devices()
    if step == "region-pack":
        context |= _region_pack_context(request)
    return render(request, f"setup/{step}.html", context)


def _confidence_from_percentage(raw: str) -> str:
    """
    A percentage typed on the detection step, as the confidence the settings API stores.

    Anything that is not a number is handed back untouched, so the parser refuses it with
    the message it gives any other unusable value rather than this reporting a different
    one.
    """
    try:
        return str(float(raw) / 100)
    except ValueError:
        return raw


def _percentages(settings: dict[str, Any]) -> dict[str, int]:
    """
    The confidence thresholds as whole percentages, for the fields to be drawn with.
    """
    return {
        key.value: round(float(settings[key.value]) * 100)
        for key in PERCENTAGE_FIELDS
        if settings.get(key.value) is not None
    }


def _region_pack_context(request: HttpRequest) -> dict[str, Any]:
    """
    What the pack step needs: which pack covers the coordinates given one step ago.

    Read from the answers rather than from the settings, because nothing has been saved
    yet. A station with no internet, or one nobody has told where it is, gets no region pack and
    a step it can walk past, which is a working station with no seasonality charts.
    """
    answers = _answers(request)
    latitude = answers.get(SettingsKey.LOCATION_LAT.value)
    longitude = answers.get(SettingsKey.LOCATION_LON.value)
    if latitude is None or longitude is None:
        return {"region_pack_unavailable": "no_location"}

    try:
        choice = region_packs_logic.choose_for(float(latitude), float(longitude))
    except (requests.RequestException, ValueError):
        # Logged rather than only shown. The step says "could not be reached", which is
        # all its reader can do anything about, and leaves whoever is looking at the
        # journal with no idea whether it was the network, a 404 or an index that could
        # not be read.
        logger.warning("Could not read the region pack index from %s", region_packs.INDEX_URL, exc_info=True)
        return {"region_pack_unavailable": "index_unavailable"}

    if choice.region_pack is None:
        return {"region_pack_unavailable": "no_packs"}
    return {
        "region_pack": choice.region_pack,
        "region_pack_name": choice.region_pack.name_in(_language(request)),
        "region_pack_covers": choice.covers,
        "region_pack_distance_km": None if choice.distance_km is None else round(choice.distance_km),
        "region_pack_request_url": region_packs_logic.REGION_PACK_REQUEST_URL,
        "region_pack_species_count": choice.region_pack.species_count,
        "region_pack_megabytes": round(choice.region_pack.size_bytes / 1_000_000),
        "installed_region_pack_id": region_packs_logic.installed_region_pack_id(),
    }


def _language(request: HttpRequest) -> str:
    """
    The language this visitor picked on the first step, English until they pick.
    """
    chosen = request.session.get(SESSION_LANGUAGE)
    return str(chosen) if chosen in dict(LANGUAGE_OPTIONS) else DEFAULT_LANGUAGE


def _chosen_language(request: HttpRequest) -> str:
    submitted = request.POST.get("language", "")
    return submitted if submitted in dict(LANGUAGE_OPTIONS) else DEFAULT_LANGUAGE
