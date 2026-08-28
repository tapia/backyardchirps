from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.features.overrides.logic import clear_queue_for_global_bar
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.shared.http import request_body


@api_view(["GET", "PUT"])
@permission_classes([IsAdminUser])
def app_settings(request: Request) -> Response:
    """
    Read or change the app settings. PUT takes as few or as many fields as it likes, and
    reports an unknown key or a bad value against the field it came from.

    Lowering the auto-confirm bar publishes the detections that were only waiting on the
    old one.
    """
    if request.method == "PUT":
        errors: dict[str, str] = {}
        previous_bar = Settings.get(SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE)

        for key, value in request_body(request).items():
            try:
                Settings.set(key, value)
            except ValueError as exc:
                errors[key] = str(exc)

        if errors:
            return Response({"errors": errors}, status=400)

        clear_queue_for_global_bar(previous_bar)

    return Response(Settings.as_dict())
