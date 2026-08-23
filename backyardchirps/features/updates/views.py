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
    What the last check found. Reads the stored result and never fetches: the timer owns
    the network call, so opening the page doesn't cost a request to GitHub.
    """
    result = updates_queries.last_check()
    if result is None:
        return Response(
            {
                "running_version": settings.VERSION,
                "checked_at": None,
                "update_available": False,
                "version": "",
                "released": "",
                "changelog_url": "",
                "error": "",
            }
        )

    return Response(
        {
            "running_version": settings.VERSION,
            "checked_at": result.checked_at,
            "update_available": updates_logic.is_newer_than_current_version(result.version),
            "version": result.version,
            "released": result.released,
            "changelog_url": result.changelog_url,
            "error": result.error,
        }
    )


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
    }
