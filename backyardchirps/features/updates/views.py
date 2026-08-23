from django.conf import settings
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.features.updates import logic as updates_logic
from backyardchirps.features.updates import queries as updates_queries


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
