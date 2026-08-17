from enum import Enum
from pathlib import Path

from django.http import FileResponse
from django.http import Http404
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps import settings
from backyardchirps.features.detections.queries import count_species_recordings
from backyardchirps.features.detections.queries import get_species_recordings
from backyardchirps.features.detections.queries import get_species_stats
from backyardchirps.features.detections.queries import species_with_detection_counts
from backyardchirps.features.overrides import queries as override_queries
from backyardchirps.features.overrides.views import detection_settings_state
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.species import queries
from backyardchirps.features.species.entity import Species
from backyardchirps.features.species.seasonality import get_yearly_seasonality
from backyardchirps.integrations.xeno_canto import get_recordings as get_xeno_canto_recordings
from backyardchirps.shared.http import get_detected_species_or_404
from backyardchirps.shared.http import get_species_or_404
from backyardchirps.shared.http import parse_dt
from backyardchirps.shared.http import resolve_confidence_level


class SpeciesListOrder(Enum):
    MOST_FREQUENT = "most_frequent"
    MOST_RECENT = "most_recent"
    ALPHABETICAL = "alphabetical"


@api_view(["GET"])
def species_list(request: Request) -> Response:
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    start, end = parse_dt(request.GET.get("start")), parse_dt(request.GET.get("end"))
    min_confidence = resolve_confidence_level(request)
    order = _parse_species_order(request.GET.get("sort"))

    db_order = order.value if order != SpeciesListOrder.ALPHABETICAL else None
    species_counts = species_with_detection_counts(start, end, min_confidence, db_order)

    if order == SpeciesListOrder.ALPHABETICAL:
        species_counts.sort(key=lambda entry: entry.species.common_name(lang))

    return Response(
        {
            "species": [
                {
                    "slug": entry.species.slug,
                    "scientific_name": entry.species.scientific_name,
                    "common_name": entry.species.common_name(lang),
                    "last_seen": entry.last_seen,
                    "count_in_period": entry.count_in_period,
                    "count_total": entry.count_total,
                    "image_url": entry.species.image_url,
                }
                for entry in species_counts
            ],
            "sort": order.value,
            "lang": lang,
        }
    )


@api_view(["GET"])
def taxonomy_search(request: Request) -> Response:
    query = request.GET.get("q", "").strip()
    language = request.GET.get("lang", settings.LANGUAGE_CODE)

    if len(query) < 2:
        return Response({"species": []})

    return Response({"species": Species.search(query, language)})


@api_view(["GET"])
def species_detail(request: Request, slug: str) -> Response:
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    start, end = parse_dt(request.GET.get("start")), parse_dt(request.GET.get("end"))
    min_confidence = resolve_confidence_level(request)
    species = get_species_or_404(slug)

    override = override_queries.get(species)
    # A blacklisted species looks like it was never detected. Its history is still in the
    # database, but stays hidden until it leaves the blacklist.
    blacklisted = override is not None and override.blacklisted
    has_detections = not blacklisted and queries.has_been_detected(species)
    if has_detections:
        detection_stats = get_species_stats(species, start, end, min_confidence)
        # The recordings tab ignores the selected period and shows everything, so its
        # count has to cover every clip we have.
        recordings_total = count_species_recordings(species)
    else:
        detection_stats = {"last_seen": None, "count_total": 0}
        recordings_total = 0

    return Response(
        {
            "slug": slug,
            "scientific_name": species.scientific_name,
            "common_name": species.common_name(lang),
            "description": species.description(lang),
            "has_detections": has_detections,
            "last_seen": detection_stats["last_seen"],
            "count_total": detection_stats["count_total"],
            "image_url": species.image_url,
            "map_url": species.map_url,
            "external_links": species.external_links(lang),
            "sounds": get_xeno_canto_recordings(Settings.get(SettingsKey.XENO_CANTO_API_KEY), species.scientific_name),
            "recordings_total": recordings_total,
            "detection_settings": detection_settings_state(override),
        }
    )


@api_view(["GET"])
def species_recordings(request: Request, slug: str) -> Response:
    start, end = parse_dt(request.GET.get("start")), parse_dt(request.GET.get("end"))
    sort = request.GET.get("sort", "date")
    direction = request.GET.get("direction", "desc")
    offset = _parse_int(request.GET.get("offset"), default=0)
    limit = _parse_int(request.GET.get("limit"), default=30)

    species = get_detected_species_or_404(slug)
    recordings, total = get_species_recordings(species, sort, direction, start, end, offset, limit)
    clips_base = Path(settings.CLIPS["save_dir"])

    return Response(
        {
            "recordings": [_recording_entry(recording, clips_base) for recording in recordings],
            "total": total,
        }
    )


@api_view(["GET"])
def species_seasonality(request: Request, slug: str) -> Response:
    # Seasonality depends only on the species and the location, not on what we have
    # heard, so this answers for any species with eBird data even if it has never been
    # recorded here. Species without that data get {"timeline": null}.
    species = get_species_or_404(slug)
    timeline = get_yearly_seasonality(species)
    return Response({"timeline": timeline})


_ASSET_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _asset_category_dirs() -> dict[str, Path]:
    """
    Where each kind of asset lives. Images ship with the code and are the same everywhere,
    while range maps are drawn around one region and come from the installed pack.
    """
    return {
        "images": settings.SPECIES_IMAGES_DIR,
        "range_maps": settings.SPECIES_RANGE_MAPS_DIR,
    }


@api_view(["GET"])
def serve_species_asset(request: Request, category: str, filename: str) -> FileResponse:
    """
    Serve a bird image or a range map. The directory layout is in
    docs/devel/species-data.md.
    """
    category_dirs = _asset_category_dirs()
    if category not in category_dirs:
        raise Http404()
    assets_dir = category_dirs[category].resolve()
    asset_path = (assets_dir / filename).resolve()
    content_type = _ASSET_CONTENT_TYPES.get(asset_path.suffix.lower())
    if asset_path.parent != assets_dir or content_type is None or not asset_path.is_file():
        raise Http404()
    return FileResponse(asset_path.open("rb"), content_type=content_type)


def _parse_species_order(value: str | None) -> SpeciesListOrder:
    for member in SpeciesListOrder:
        if member.value == value:
            return member
    return SpeciesListOrder.MOST_FREQUENT


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _recording_entry(recording: dict, clips_base: Path) -> dict:
    clip_path = Path(recording["clip_path"])
    try:
        clip_rel = clip_path.relative_to(clips_base)
    except ValueError:
        clip_rel = Path(clip_path.name)
    return {
        "id": recording["id"],
        "recorded_at": recording["recorded_at"],
        "confidence": recording["confidence"],
        "clip_url": f"/api/clips/{clip_rel}",
        "length_seconds": recording["clip_duration_seconds"],
        "validation_status": recording["validation_status"],
    }
