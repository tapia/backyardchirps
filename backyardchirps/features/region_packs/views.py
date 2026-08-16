import logging
from typing import Any

import requests
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.features.region_packs import install_status
from backyardchirps.features.region_packs import logic as region_packs_logic
from backyardchirps.features.region_packs.entity import RegionPack
from backyardchirps.features.region_packs.entity import RegionPackChoice
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.setup.permissions import IsSetupAuthorised
from backyardchirps.integrations import region_packs

logger = logging.getLogger(__name__)


@api_view(["GET"])
@permission_classes([IsSetupAuthorised | IsAdminUser])
def region_pack(request: Request) -> Response:
    """
    Which pack covers a point, or the nearest one when none does.

    Open to the wizard as well as to an admin, because the wizard asks this before there
    is a session to be an admin in, and the settings page asks the same question later
    when somebody moves the station. One endpoint, so the two cannot drift apart on what
    counts as a match.

    The coordinates come from the query string rather than from the saved location: on the
    wizard's pack step nothing has been saved yet.
    """
    latitude = _coordinate(request, "lat", limit=90.0)
    longitude = _coordinate(request, "lon", limit=180.0)
    if latitude is None or longitude is None:
        return Response({"error": "invalid_coordinates"}, status=400)

    try:
        choice = region_packs_logic.choose_for(latitude, longitude)
    except (requests.RequestException, ValueError):
        # A station with no internet during setup is a working station. It gets no pack,
        # which is a state everything downstream already copes with.
        logger.warning("Could not read the region pack index from %s", region_packs.INDEX_URL, exc_info=True)
        return Response({"error": "index_unavailable"}, status=503)

    return Response(_as_choice(choice))


@api_view(["GET"])
@permission_classes([IsSetupAuthorised | IsAdminUser])
def installed_region_pack(request: Request) -> Response:
    """
    The pack this station has, if any. Answers from the recorded id and the disk together,
    so a station whose data directory was restored without its packs says so.
    """
    return Response(
        {
            "id": region_packs_logic.installed_region_pack_id() or None,
            "installed": region_packs_logic.pack_is_installed(),
        }
    )


@api_view(["POST"])
@permission_classes([IsSetupAuthorised | IsAdminUser])
def install_region_pack(request: Request) -> Response:
    """
    Begin installing a pack. Answers straight away and leaves it running.

    A pack takes minutes on a Pi, so this cannot be the request that downloads it: the
    browser would be holding a connection open for the whole thing, and a screen that
    locks would end it. Ask install_progress how it is going.
    """
    wanted = str(request.data.get("id", "")) if isinstance(request.data, dict) else ""
    if not wanted:
        return Response({"error": "no_pack_given"}, status=400)

    try:
        packs = region_packs_logic.available_packs()
    except (requests.RequestException, ValueError):
        logger.warning("Could not read the region pack index from %s", region_packs.INDEX_URL, exc_info=True)
        return Response({"error": "index_unavailable"}, status=503)

    # Looked up in the index rather than taken from the request. The URL and the checksum
    # decide what gets downloaded and whether it is trusted, so they may only come from
    # the index, never from whoever is asking.
    chosen = next((pack for pack in packs if pack.id == wanted), None)
    if chosen is None:
        return Response({"error": "unknown_pack"}, status=404)

    if not region_packs_logic.start_install(chosen):
        return Response({"error": "already_installing"}, status=409)
    return Response(_as_progress(), status=202)


@api_view(["GET"])
@permission_classes([IsSetupAuthorised | IsAdminUser])
def install_progress(request: Request) -> Response:
    """
    How far the install has got. Polled by the wizard's pack step.
    """
    return Response(_as_progress())


def _as_progress() -> dict[str, Any]:
    progress = install_status.read()
    if progress is None:
        return {"state": None}
    return {
        "state": str(progress.state),
        "pack_id": progress.pack_id,
        "received_bytes": progress.received_bytes,
        "total_bytes": progress.total_bytes,
        "fraction": progress.fraction,
        "error": progress.error,
    }


def _coordinate(request: Request, name: str, limit: float) -> float | None:
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if -limit <= value <= limit else None


def _as_choice(choice: RegionPackChoice) -> dict[str, Any]:
    language = Settings.get(SettingsKey.NOTIFICATIONS_LANGUAGE)
    return {
        "covers": choice.covers,
        "distance_km": None if choice.distance_km is None else round(choice.distance_km),
        "region_pack": None if choice.region_pack is None else _as_region_pack(choice.region_pack, language),
    }


def _as_region_pack(pack: RegionPack, language: str) -> dict[str, Any]:
    return {
        "id": pack.id,
        "name": pack.name_in(language),
        "version": pack.version,
        "species_count": pack.species_count,
        "size_bytes": pack.size_bytes,
    }
