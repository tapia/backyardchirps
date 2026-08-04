from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.features.settings.logic import Settings


@api_view(["GET", "PUT"])
@permission_classes([IsAdminUser])
def app_settings(request: Request) -> Response:
    """
    Read or change the app settings. PUT takes as few or as many fields as it likes, and
    reports an unknown key or a bad value against the field it came from.
    """
    if request.method == "PUT":
        errors: dict[str, str] = {}

        for key, value in request.data.items():
            try:
                Settings.set(key, value)
            except ValueError as exc:
                errors[key] = str(exc)

        if errors:
            return Response({"errors": errors}, status=400)

    return Response(Settings.as_dict())
