from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from typing import cast

from django.conf import settings
from django.db import transaction
from django.db.models import Case
from django.db.models import Count
from django.db.models import Exists
from django.db.models import F
from django.db.models import FloatField
from django.db.models import Max
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models import Value
from django.db.models import When
from django.db.models.functions import Round

from backyardchirps.features.detections.entity import AnalysisCandidate
from backyardchirps.features.detections.entity import Detection
from backyardchirps.features.detections.entity import SpeciesAlreadyIdentifiedException
from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.features.overrides import queries as override_queries
from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.recording.audio.detection import AnalysisResult
from backyardchirps.features.recording.audio.detection import RawCandidate
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.species.entity import Species
from backyardchirps.models.detected_species import DetectedSpecies
from backyardchirps.models.stored_detection import StoredDetection
from backyardchirps.models.stored_detection import StoredDetectionQuerySet


@dataclass(frozen=True)
class SpeciesDetectionCounts:
    """
    Detection statistics for one species, as returned by species_with_detection_counts.
    """

    species: Species
    last_seen: datetime | None
    count_total: int
    count_in_period: int


def get_by_id(pk: int) -> Detection:
    """
    Raises StoredDetection.DoesNotExist when there is no such row, and also when its
    species has since left the taxonomy.
    """
    stored_detection = StoredDetection.objects.select_related("species", "original_species").get(pk=pk)
    detection = stored_detection.to_entity()
    if detection is None:
        raise StoredDetection.DoesNotExist(f"Detection {pk} references a species missing from the taxonomy")
    return detection


def list_detections(
    offset: int = 0,
    limit: int = 50,
    species: Species | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> tuple[list[dict], int]:
    """
    A page of detections, newest first, plus the total number that matched.

    Unlike everywhere else on the site, this includes the detections still waiting for
    review: it is the one page that shows everything the station heard, and it says which
    rows are pending rather than leaving them out.

    Can be narrowed to one species and to a [start, end] date range. A filter left as
    None is not applied.
    """
    queryset = StoredDetection.objects.excluding_blacklisted().in_period(start, end)
    if species is not None:
        queryset = queryset.of_species(species)
    queryset = queryset.order_by("-recorded_at")
    total = queryset.count()
    rows = queryset.values(
        "id",
        "recorded_at",
        "confidence",
        "analysis_time_ms",
        "validation_status",
        "species__scientific_name",
        "analysis_candidates",
    )[offset : offset + limit]
    detections = []
    for row in rows:
        scientific_name = row["species__scientific_name"]
        detections.append(
            {
                "id": row["id"],
                "recorded_at": row["recorded_at"],
                "confidence": row["confidence"],
                "analysis_time_ms": row["analysis_time_ms"],
                "validation_status": row["validation_status"],
                "scientific_name": scientific_name,
                "species": Species.from_scientific_name(scientific_name),
                "candidates": [
                    AnalysisCandidate.from_stored(candidate) for candidate in (row["analysis_candidates"] or [])
                ],
            }
        )
    return detections, total


def upsert(
    clip: AudioClip,
    analysis_result: AnalysisResult,
    analysis_time_ms: int = 0,
    raw_candidates: list[RawCandidate] | None = None,
) -> Detection | None:
    """
    Create or update the detection record for this clip's time block.

    Detections of the same species are grouped into 3-minute blocks, and each block
    keeps only its most confident one, with the longest recording of it. Since the
    analysis time and the raw candidates describe the saved clip, they are rewritten
    whenever that clip is replaced. Returns None when the stored record is already the
    better of the two, and when a person has reviewed it.
    """
    block_start = get_block_time(clip.recorded_at)
    block_end = block_start + timedelta(minutes=_detection_time_buffer_in_minutes())
    serialized_candidates = _serialize_candidates(raw_candidates)
    detected_species, _ = DetectedSpecies.objects.get_or_create(scientific_name=analysis_result.species.scientific_name)
    existing = (
        StoredDetection.objects.select_related("species")
        .filter(species=detected_species, recorded_at__gte=block_start, recorded_at__lt=block_end)
        .first()
    )

    if existing is None:
        clip_path = clip.save_if_needed(analysis_result)
        created = StoredDetection.objects.create(
            species=detected_species,
            recorded_at=clip.recorded_at,
            confidence=analysis_result.confidence,
            clip_path=str(clip_path),
            clip_duration_seconds=clip.duration_seconds(),
            validation_status=_initial_validation_status(analysis_result.confidence, analysis_result.species),
            analysis_time_ms=analysis_time_ms,
            analysis_candidates=serialized_candidates,
        )
        return created.to_entity()

    if existing.validation_status == ValidationStatus.HUMAN_CONFIRMED:
        return None

    if not _is_better_record(analysis_result.confidence, clip.duration_seconds(), existing):
        return None

    if existing.clip_path:
        AudioClip.delete_clip(existing.clip_path)
    new_clip_path = clip.save_if_needed(analysis_result)

    existing.confidence = analysis_result.confidence
    existing.recorded_at = clip.recorded_at
    existing.clip_path = str(new_clip_path)
    existing.clip_duration_seconds = clip.duration_seconds()
    existing.validation_status = _initial_validation_status(analysis_result.confidence, analysis_result.species)
    existing.analysis_time_ms = analysis_time_ms
    existing.analysis_candidates = serialized_candidates
    existing.save(
        update_fields=[
            "confidence",
            "recorded_at",
            "clip_path",
            "clip_duration_seconds",
            "validation_status",
            "analysis_time_ms",
            "analysis_candidates",
        ]
    )
    return existing.to_entity()


def species_with_detection_counts(
    start: datetime | None = None,
    end: datetime | None = None,
    order: str | None = None,
) -> list[SpeciesDetectionCounts]:
    """
    Detection statistics per species, counting only what the site shows. Pass
    "most_recent" or "most_frequent" as order, or None to leave the results unsorted.
    """
    approved_q = Q(detections__validation_status__in=ValidationStatus.approved())

    period_q = approved_q
    if start:
        period_q &= Q(detections__recorded_at__gte=start)
    if end:
        period_q &= Q(detections__recorded_at__lte=end)

    queryset = (
        DetectedSpecies.objects.annotate(
            last_seen=Max("detections__recorded_at", filter=approved_q),
            count_total=Count("detections", filter=approved_q),
            count_in_period=Count("detections", filter=period_q),
        )
        .filter(count_total__gt=0)
        .exclude(override__blacklisted=True)
    )

    if start or end:
        exists_queryset = StoredDetection.objects.filter(species=OuterRef("pk")).approved().in_period(start, end)
        queryset = queryset.filter(Exists(exists_queryset))

    if order == "most_recent":
        queryset = queryset.order_by("-last_seen")
    elif order == "most_frequent":
        queryset = queryset.order_by("-count_in_period")

    results = []
    for row in queryset:
        species = row.to_entity()
        if species is None:
            continue
        results.append(
            SpeciesDetectionCounts(
                species=species,
                last_seen=row.last_seen,
                count_total=row.count_total,
                count_in_period=row.count_in_period,
            )
        )
    return results


def get_species_stats(
    species: Species,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict:
    """
    Note that the two answer slightly different questions: last_seen is the most recent
    detection ever, ignoring start and end, while count_total counts only the period
    asked for. Both count only what the site shows.
    """
    approved_q = Q(validation_status__in=ValidationStatus.approved())
    period_q = approved_q
    if start:
        period_q &= Q(recorded_at__gte=start)
    if end:
        period_q &= Q(recorded_at__lte=end)

    return StoredDetection.objects.of_species(species).aggregate(
        last_seen=Max("recorded_at", filter=approved_q),
        count_total=Count("id", filter=period_q),
    )


def get_species_recordings(
    species: Species,
    sort: str = "date",
    direction: str = "desc",
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = 0,
    limit: int = 30,
) -> tuple[list[dict], int]:
    """
    A page of the species' detections that still have a saved clip, plus the total
    number that matched. Order them by `sort` ("date" or "confidence") and `direction`
    ("asc" or "desc").
    """
    queryset = _species_recordings_queryset(species, start, end)
    total = queryset.count()
    if sort == "confidence":
        # Sort by the confidence as the UI shows it, rounded to a whole percent. Two rows
        # displaying the same percentage then stay together, newest first, instead of
        # being separated by decimals nobody can see.
        queryset = queryset.annotate(display_confidence=Round(_effective_confidence() * 100))
        primary = "display_confidence" if direction == "asc" else "-display_confidence"
        ordering = [primary, "-recorded_at"]
    else:
        ordering = ["recorded_at" if direction == "asc" else "-recorded_at"]
    rows = queryset.order_by(*ordering).values(
        "id", "recorded_at", "confidence", "clip_path", "clip_duration_seconds", "validation_status"
    )[offset : offset + limit]
    return [dict(row) for row in rows], total


def count_species_recordings(
    species: Species,
    start: datetime | None = None,
    end: datetime | None = None,
) -> int:
    """
    Return the number of detections of the species that have saved clips.
    """
    return _species_recordings_queryset(species, start, end).count()


def get_oldest_clips(limit: int) -> list[dict]:
    """
    The `limit` oldest clips across all detections, which is the order in which the disk
    quota deletes them.
    """
    rows = StoredDetection.objects.with_saved_clip().order_by("recorded_at").values("id", "clip_path")[:limit]
    return [dict(row) for row in rows]


def clear_clip_path(detection_id: int) -> None:
    """
    Record that the detection no longer has a saved clip file.
    """
    StoredDetection.objects.filter(pk=detection_id).update(clip_path=None)


def get_dubious_detections() -> list[Detection]:
    """
    Return all detections still awaiting human review, ordered newest first.
    """
    stored_detections = (
        StoredDetection.objects.filter(validation_status=ValidationStatus.PENDING)
        .excluding_blacklisted()
        .select_related("species")
        .order_by("-recorded_at")
    )
    detections = [stored_detection.to_entity() for stored_detection in stored_detections]
    return [detection for detection in detections if detection is not None]


def count_dubious_detections() -> int:
    return StoredDetection.objects.filter(validation_status=ValidationStatus.PENDING).excluding_blacklisted().count()


def species_identified_in_same_recording(detection: Detection) -> list[Species]:
    """
    The other species identified in the detection's recording, itself excluded.

    Like anywhere else, blacklisted species are left out.
    """
    stored_detections = (
        StoredDetection.objects.recorded_with(detection.recorded_at)
        .exclude(pk=detection.id)
        .excluding_blacklisted()
        .select_related("species")
    )
    identified = []
    for stored_detection in stored_detections:
        species = stored_detection.species.to_entity()
        if species is not None:
            identified.append(species)
    return identified


def has_detection_before(species: Species, before_dt: datetime) -> bool:
    return StoredDetection.objects.of_species(species).filter(recorded_at__lt=before_dt).exists()


def has_detection_in_range(
    species: Species,
    since_dt: datetime,
    before_dt: datetime,
    min_confidence: float,
) -> bool:
    """
    Return True if any detection of the species exists in [since_dt, before_dt),
    filtered by minimum confidence.
    """
    queryset = StoredDetection.objects.of_species(species).filter(
        recorded_at__gte=since_dt,
        recorded_at__lt=before_dt,
        confidence__gte=min_confidence,
    )
    return queryset.exists()


def confirm(detection_id: int, reassigned_species: Species | None = None) -> None:
    """
    Record a human confirmation of the detection, optionally changing its species.

    Raises StoredDetection.DoesNotExist when there is no such row, and
    SpeciesAlreadyIdentifiedException when the new species is already identified in the
    same recording.
    """
    detection = StoredDetection.objects.get(pk=detection_id)
    if reassigned_species is None:
        detection.confirm()
        return

    already_identified = (
        StoredDetection.objects.recorded_with(detection.recorded_at)
        .of_species(reassigned_species)
        .exclude(pk=detection.pk)
        .exists()
    )
    if already_identified:
        raise SpeciesAlreadyIdentifiedException(
            f"{reassigned_species.scientific_name} is already identified in this recording."
        )
    detection.confirm(reassigned_species)


def discard(detection_id: int) -> None:
    """
    Delete the detection's clip file and its row. Raises StoredDetection.DoesNotExist
    when there is no such row.
    """
    StoredDetection.objects.get(pk=detection_id).discard()


def confirm_many(detection_ids: list[int]) -> list[int]:
    """
    Human-confirm several detections at once, each keeping its own species.
    """
    confirmed_ids: list[int] = []
    with transaction.atomic():
        for detection in StoredDetection.objects.filter(pk__in=detection_ids):
            detection.confirm()
            confirmed_ids.append(detection.id)
    return confirmed_ids


def discard_many(detection_ids: list[int]) -> list[int]:
    """
    Delete several detections and their clip files, returning the ids removed.
    """
    discarded_ids: list[int] = []
    for detection in StoredDetection.objects.filter(pk__in=detection_ids):
        # discard() deletes the row, and that sets the instance pk to None, so read the
        # id before calling it.
        detection_id = detection.id
        detection.discard()
        discarded_ids.append(detection_id)
    return discarded_ids


def auto_confirm_pending_above(species: Species, threshold: float) -> int:
    """
    Called after the auto-confirm bar for a species is lowered, to clear the detections
    that were only waiting because the old bar was higher. PENDING rows at or above
    `threshold` become AUTO_CONFIRMED and keep their own confidence, which is never
    rewritten to 1.0. Rows a human already confirmed are left alone.

    Returns how many rows changed.
    """
    return (
        StoredDetection.objects.of_species(species)
        .filter(validation_status=ValidationStatus.PENDING, confidence__gte=threshold)
        .update(validation_status=ValidationStatus.AUTO_CONFIRMED)
    )


def auto_confirm_pending_above_default(threshold: float) -> int:
    """
    The same, for a lowered global bar rather than one species' own.

    A species that has its own threshold is left alone: its detections wait on that
    number, and the global one says nothing about them.

    Returns how many rows changed.
    """
    return (
        StoredDetection.objects.filter(validation_status=ValidationStatus.PENDING, confidence__gte=threshold)
        .exclude(species__override__auto_confirm_threshold__isnull=False)
        .update(validation_status=ValidationStatus.AUTO_CONFIRMED)
    )


def get_block_time(dt: datetime) -> datetime:
    """
    The start of the batch window a moment falls in.
    """
    buffer_minutes = _detection_time_buffer_in_minutes()
    return dt.replace(
        minute=(dt.minute // buffer_minutes) * buffer_minutes,
        second=0,
        microsecond=0,
    )


def _detection_time_buffer_in_minutes() -> int:
    return settings.RECORDING["detection_time_buffer_in_minutes"]


def _species_recordings_queryset(
    species: Species,
    start: datetime | None = None,
    end: datetime | None = None,
) -> StoredDetectionQuerySet:
    return StoredDetection.objects.of_species(species).approved().with_saved_clip().in_period(start, end)


def _serialize_candidates(raw_candidates: list[RawCandidate] | None) -> list[dict] | None:
    """
    Turn the raw candidates into the JSON shape kept on the row, or None when there is
    nothing to store.
    """
    if not raw_candidates:
        return None
    return [{"label": candidate.label, "confidence": candidate.confidence} for candidate in raw_candidates]


def _effective_confidence() -> Case:
    """
    Confidence as the site treats it, for sorting.

    A detection a person has validated counts as fully confident whatever BirdNET scored
    it, and sorts above the rest. The stored number is left as the model reported it, so
    this belongs in the query rather than in the row.
    """
    return Case(
        When(validation_status=ValidationStatus.HUMAN_CONFIRMED, then=Value(1.0)),
        default=F("confidence"),
        output_field=FloatField(),
    )


def _is_better_record(confidence: float, duration_seconds: float | None, existing: StoredDetection) -> bool:
    """
    Whether the clip just analyzed should replace the one stored for this block.

    A more confident hearing always wins. At the same confidence the longer recording
    wins: the consistency window reports a species again on every clip it is heard in,
    with more of the window stitched together each time, and the reviewer should end up
    with the longest of those rather than the first.

    A lower confidence never wins, even with more audio. The window slides, so once the
    best clip has left it a later hearing reports a smaller maximum, and the stored one
    is still the better record.
    """
    if confidence != existing.confidence:
        return confidence > existing.confidence
    return (duration_seconds or 0.0) > (existing.clip_duration_seconds or 0.0)


def _initial_validation_status(confidence: float, species: Species) -> ValidationStatus:
    if confidence < _auto_confirm_bar(species):
        return ValidationStatus.PENDING
    return ValidationStatus.AUTO_CONFIRMED


def _auto_confirm_bar(species: Species) -> float:
    """
    The confidence at which a detection of this species is confirmed without human
    review. The species' own threshold wins when it has one, otherwise the global bar
    applies.
    """
    custom_threshold = override_queries.auto_confirm_threshold(species)
    if custom_threshold is not None:
        return custom_threshold
    return cast(float, Settings.get(SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE))
