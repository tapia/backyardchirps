from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from backyardchirps import settings
from backyardchirps.features.overrides import logic
from backyardchirps.features.overrides import queries
from backyardchirps.features.overrides.entity import SpeciesOverride
from backyardchirps.features.species import queries as species_queries
from backyardchirps.shared.http import get_species_or_404


@api_view(["GET"])
@permission_classes([IsAdminUser])
def detection_settings_list(request):
    """
    Every species with custom detection settings, for the admin page.
    """
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    return Response(
        {
            "species": [
                {
                    "slug": override.species.slug,
                    "scientific_name": override.species.scientific_name,
                    "common_name": override.species.common_name(lang),
                    "image_url": override.species.image_url,
                    **detection_settings_state(override),
                }
                for override in queries.list_customized()
            ]
        }
    )


@api_view(["GET", "PUT", "DELETE"])
def species_detection_settings(request, slug):
    """
    A species' blacklisted state and auto-confirm threshold. Anyone can read them, only
    staff can change them.

    PUT merges what it is given onto the current settings, so the two fields can be
    changed one at a time. DELETE goes back to the global defaults.
    """
    species = get_species_or_404(slug)
    if not species_queries.has_been_detected(species):
        raise NotFound() from None

    if request.method == "GET":
        return Response(detection_settings_state(queries.get(species)))

    if not request.user.is_staff:
        return Response({"error": "Staff only"}, status=403)

    if request.method == "DELETE":
        logic.clear_override(species)
        return Response(status=204)

    try:
        auto_confirm_threshold, blacklisted = _parse_override_body(request.data, queries.get(species))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    result = logic.set_override(species, auto_confirm_threshold, blacklisted)
    return Response(detection_settings_state(result))


def detection_settings_state(override: SpeciesOverride | None) -> dict:
    """
    The detection-settings payload the frontend expects. A species with no override at
    all still gets one, filled with the defaults.
    """
    return {
        "blacklisted": override.blacklisted if override is not None else False,
        "auto_confirm_threshold": override.auto_confirm_threshold if override is not None else None,
    }


def _parse_override_body(body: dict, current: SpeciesOverride | None) -> tuple[float | None, bool]:
    """
    Merge the request body onto the current override, checking each field. A field the
    body leaves out keeps the value it has.
    """
    blacklisted = current.blacklisted if current is not None else False
    if "blacklisted" in body:
        if not isinstance(body["blacklisted"], bool):
            raise ValueError("blacklisted must be a boolean")
        blacklisted = body["blacklisted"]

    threshold = current.auto_confirm_threshold if current is not None else None
    if "auto_confirm_threshold" in body:
        threshold = _parse_threshold(body["auto_confirm_threshold"])

    return threshold, blacklisted


def _parse_threshold(value: object) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError("auto_confirm_threshold must be a number between 0 and 1") from None
    if not 0 <= parsed <= 1:
        raise ValueError("auto_confirm_threshold must be a number between 0 and 1")
    return parsed
