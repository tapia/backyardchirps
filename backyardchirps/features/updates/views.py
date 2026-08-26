from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.features.updates import logic as updates_logic
from backyardchirps.features.updates import queries as updates_queries
from backyardchirps.features.updates.logic import UpdateRefused
from backyardchirps.features.updates.progress import read_progress
from backyardchirps.shared.http import request_body


@api_view(["GET"])
@permission_classes([IsAdminUser])
def available_update(request: Request) -> Response:
    """
    What the last check found. Reads the stored result and never looks at the repository
    itself: that needs root, so a unit does it and opening the page costs nothing.
    """
    return Response(_available_body())


@api_view(["POST"])
@permission_classes([IsAdminUser])
def check_for_update(request: Request) -> Response:
    """
    Look at the repository now, rather than waiting for the daily timer.

    The unit is a oneshot, so starting it waits for it to finish, and by the time this
    answers the stored result is the fresh one.
    """
    try:
        updates_logic.start_check()
    except UpdateRefused as refusal:
        return Response({"error": str(refusal)}, status=409)

    return Response(_available_body())


def _available_body() -> dict[str, object]:
    result = updates_queries.last_check()
    if result is None:
        return {
            "running_version": settings.VERSION,
            "checked_at": None,
            "update_available": False,
            "version": "",
            "released": "",
            "changelog_url": "",
            "error": "",
        }

    return {
        "running_version": settings.VERSION,
        "checked_at": result.checked_at,
        "update_available": result.update_available,
        "version": result.version,
        "released": result.released,
        "changelog_url": result.changelog_url,
        "error": result.error,
    }


@api_view(["POST"])
@permission_classes([IsAdminUser])
def apply_update(request: Request) -> Response:
    """
    Ask the station to install a version. Admin only, like everything else here.

    The body names the version so that clicking a badge for 0.3.0 cannot install whatever
    happens to be latest by the time the request lands. A version that no longer matches
    the last check is refused rather than upgraded to.
    """
    version = str(request_body(request).get("version", ""))
    try:
        updates_logic.start_update(version)
    except UpdateRefused as refusal:
        return Response({"error": str(refusal)}, status=409)

    return Response(_progress_body(), status=202)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def update_progress(request: Request) -> Response:
    """
    What the updater is doing. Polled while an update runs.
    """
    return Response(_progress_body())


def _progress_body() -> dict[str, str]:
    progress = read_progress()
    return {
        "state": progress.state,
        "version": progress.version,
        "step": progress.step,
        "message": progress.message,
        "updated_at": progress.updated_at,
    }


@api_view(["POST"])
@permission_classes([IsAdminUser])
def rollback_update(request: Request) -> Response:
    """
    Go back to the version running before the last update. Admin only, like everything
    else here.
    """
    try:
        updates_logic.start_rollback()
    except UpdateRefused as refusal:
        return Response({"error": str(refusal)}, status=409)

    return Response(_progress_body(), status=202)
