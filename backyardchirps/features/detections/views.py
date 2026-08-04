import re
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.http import FileResponse
from django.http import HttpResponse
from django.http import HttpResponseBase
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps import settings
from backyardchirps.features.detections.entity import SpeciesAlreadyIdentifiedException
from backyardchirps.features.detections.queries import confirm as confirm_detection
from backyardchirps.features.detections.queries import confirm_many
from backyardchirps.features.detections.queries import count_dubious_detections
from backyardchirps.features.detections.queries import discard as discard_detection
from backyardchirps.features.detections.queries import discard_many
from backyardchirps.features.detections.queries import get_by_id
from backyardchirps.features.detections.queries import get_dubious_detections
from backyardchirps.features.detections.queries import list_detections
from backyardchirps.features.detections.queries import species_identified_in_same_recording
from backyardchirps.features.overrides import queries as species_override_repository
from backyardchirps.features.species.entity import Species
from backyardchirps.shared.http import _parse_dt


@api_view(["POST", "DELETE"])
def validate_detection(request, pk):
    try:
        if request.method == "POST":
            confirm_detection(pk, _reassigned_species(request))
            return Response(status=200)
        discard_detection(pk)
        return Response(status=204)
    except SpeciesAlreadyIdentifiedException as already_identified:
        raise ValidationError({"species_scientific_name": str(already_identified)}) from None
    except ObjectDoesNotExist:
        raise NotFound() from None


@api_view(["POST"])
def validate_detections(request):
    """
    Apply one review action to many detections at once. The body carries an "action",
    either "confirm" or "discard", and a non-empty "ids" list. Confirming here leaves
    every detection on its own species.
    """
    action = request.data.get("action")
    detection_ids = request.data.get("ids")
    if not isinstance(detection_ids, list) or not detection_ids:
        raise ValidationError({"ids": "A non-empty list of detection ids is required."})

    if action == "confirm":
        processed = confirm_many(detection_ids)
    elif action == "discard":
        processed = discard_many(detection_ids)
    else:
        raise ValidationError({"action": "Must be 'confirm' or 'discard'."})

    return Response({"processed": processed})


@api_view(["GET"])
def detections_list(request):
    """
    The diagnostics page feed: every detection, newest first, with its time, processing
    time and a link to follow. Can be filtered by scientific name and by a [start, end]
    date range.
    """
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    offset = _parse_int(request.GET.get("offset"), default=0)
    limit = _parse_int(request.GET.get("limit"), default=50)
    start = _parse_dt(request.GET.get("start"))
    end = _parse_dt(request.GET.get("end"))

    scientific_name = request.GET.get("species")
    if scientific_name:
        species = Species.from_scientific_name(scientific_name)
        # An unknown name matches nothing. Ignoring the filter instead would quietly
        # return every species, which looks like the filter is broken.
        if species is None:
            return Response({"total": 0, "detections": []})
    else:
        species = None

    detections, total = list_detections(offset=offset, limit=limit, species=species, start=start, end=end)
    return Response(
        {
            "total": total,
            "detections": [_detection_list_entry(detection, lang) for detection in detections],
        }
    )


@api_view(["GET"])
def dubious_detections(request):
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    clips_base = Path(settings.CLIPS["save_dir"])

    detections = [_detection_entry(detection, clips_base, lang) for detection in get_dubious_detections()]
    return Response({"count": len(detections), "detections": detections})


@api_view(["GET"])
def dubious_detections_count(request):
    return Response({"count": count_dubious_detections()})


@api_view(["GET"])
def detection_detail(request, pk):
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    clips_base = Path(settings.CLIPS["save_dir"])

    try:
        detection = get_by_id(pk)
    except ObjectDoesNotExist:
        raise NotFound() from None

    # A blacklisted species looks like it was never detected at all, so even a direct
    # link to one of its detections has to 404 until it leaves the blacklist.
    if species_override_repository.is_blacklisted(detection.species):
        raise NotFound() from None

    # Only the review dialog needs the rest of the recording, and it opens one detection
    # at a time, so this endpoint is the one that can afford the extra query.
    entry = _detection_entry(detection, clips_base, lang)
    entry["also_identified"] = [
        _identified_species_entry(species, lang) for species in species_identified_in_same_recording(detection)
    ]
    return Response(entry)


@api_view(["GET"])
def serve_clip(request: Request, filepath: str) -> HttpResponseBase:
    """
    Stream a saved audio clip. It answers HTTP range requests, without which the browser
    cannot jump to a point in the clip, and dragging on the spectrogram stops working.
    """
    clips_dir = Path(settings.CLIPS["save_dir"]).resolve()
    clip_path = (clips_dir / filepath).resolve()
    try:
        clip_path.relative_to(clips_dir)
    except ValueError:
        raise NotFound() from None
    if not clip_path.is_file():
        raise NotFound()

    file_size = clip_path.stat().st_size
    byte_range = _parse_range(request.headers.get("Range"), file_size)
    if byte_range is None:
        response: HttpResponseBase = FileResponse(clip_path.open("rb"), content_type="audio/wav")
        response["Accept-Ranges"] = "bytes"
        return response

    start, end = byte_range
    with clip_path.open("rb") as clip_file:
        clip_file.seek(start)
        chunk = clip_file.read(end - start + 1)
    response = HttpResponse(chunk, status=206, content_type="audio/wav")
    response["Accept-Ranges"] = "bytes"
    response["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    response["Content-Length"] = str(len(chunk))
    return response


def _parse_range(header: str | None, file_size: int) -> tuple[int, int] | None:
    """
    Parse a single 'bytes=start-end' HTTP Range header into an inclusive (start, end)
    pair, kept within the file. Returns None when the header is missing, malformed, or
    asks for something the file cannot give.
    """
    if not header:
        return None
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header.strip())
    if not match:
        return None
    start_text, end_text = match.group(1), match.group(2)
    if start_text == "" and end_text == "":
        return None
    if start_text == "":
        suffix_length = int(end_text)
        if suffix_length == 0:
            return None
        start = max(0, file_size - suffix_length)
        end = file_size - 1
    else:
        start = int(start_text)
        end = min(int(end_text), file_size - 1) if end_text else file_size - 1
    if start > end or start >= file_size:
        return None
    return start, end


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _detection_list_entry(detection, lang):
    return {
        "id": detection["id"],
        "recorded_at": detection["recorded_at"],
        "confidence": detection["confidence"],
        "analysis_time_ms": detection["analysis_time_ms"],
        "species": _list_species(detection["species"], detection["scientific_name"], lang),
        "candidates": [_candidate_entry(candidate, lang) for candidate in detection["candidates"]],
    }


def _list_species(species, scientific_name, lang):
    # A species the taxonomy does not know has no slug and no common name, so the row can
    # only show the scientific name we stored.
    if species is None:
        return {"slug": None, "scientific_name": scientific_name, "common_name": None}
    return {
        "slug": species.slug,
        "scientific_name": species.scientific_name,
        "common_name": species.common_name(lang),
    }


def _reassigned_species(request: Request) -> Species | None:
    scientific_name = request.data.get("species_scientific_name")
    if not scientific_name:
        return None
    species = Species.from_scientific_name(scientific_name)
    if species is None:
        raise ValidationError({"species_scientific_name": "Unknown species."})
    return species


def _detection_entry(detection, clips_base, lang):
    clip_path = Path(detection.clip_path or "")
    try:
        clip_rel = clip_path.relative_to(clips_base)
    except ValueError:
        clip_rel = Path(clip_path.name)
    return {
        "id": detection.id,
        "recorded_at": detection.recorded_at,
        "confidence": detection.confidence,
        "clip_url": f"/api/clips/{clip_rel}",
        "length_seconds": detection.clip_duration_seconds,
        "validation_status": detection.validation_status,
        "reviewed_by_human": detection.reviewed_by_human(),
        "original_detection": _original_detection(detection, lang),
        "analysis_time_ms": detection.analysis_time_ms,
        "analysis_candidates": [_candidate_entry(candidate, lang) for candidate in detection.analysis_candidates],
        "species": {
            "slug": detection.species.slug,
            "scientific_name": detection.species.scientific_name,
            "common_name": detection.species.common_name(lang),
            "image_url": detection.species.image_url,
        },
    }


def _original_detection(detection, lang):
    """
    What BirdNET originally said. Only present when a human changed the species.
    """
    if detection.original_species is None:
        return None
    return {
        "confidence": detection.original_confidence,
        "species": {
            "slug": detection.original_species.slug,
            "scientific_name": detection.original_species.scientific_name,
            "common_name": detection.original_species.common_name(lang),
        },
    }


def _identified_species_entry(species, lang):
    """
    One of the other species identified in the recording under review. The image comes
    along because the header needs it as soon as the reviewer picks this species.
    """
    return {
        "slug": species.slug,
        "scientific_name": species.scientific_name,
        "common_name": species.common_name(lang),
        "image_url": species.image_url,
    }


def _candidate_entry(candidate, lang):
    """
    One raw BirdNET candidate. Those our taxonomy knows also carry a slug and a
    translated common name. The rest, non-bird sounds among them, carry only their label.
    """
    if candidate.species is None:
        return {
            "label": candidate.label,
            "confidence": candidate.confidence,
            "slug": None,
            "scientific_name": None,
            "common_name": None,
        }
    return {
        "label": candidate.label,
        "confidence": candidate.confidence,
        "slug": candidate.species.slug,
        "scientific_name": candidate.species.scientific_name,
        "common_name": candidate.species.common_name(lang),
    }
