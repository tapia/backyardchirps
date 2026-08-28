import math
from datetime import date
from datetime import datetime
from datetime import timedelta
from enum import Enum
from typing import cast

from django.db.models import Count
from django.db.models import Min
from django.db.models import QuerySet
from django.db.models.functions import ExtractHour
from django.db.models.functions import TruncDay
from django.db.models.functions import TruncHour
from django.db.models.functions import TruncMonth
from django.utils import timezone

from backyardchirps.features.species.entity import Species
from backyardchirps.models.detected_species import DetectedSpecies
from backyardchirps.models.stored_detection import StoredDetection


class TimeGranularity(Enum):
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"


def species_detections_over_time(
    species: Species,
    start: datetime | None,
    end: datetime | None,
    min_confidence: float | None = None,
) -> tuple[list[dict], TimeGranularity]:
    """
    How many detections there were in each period, counting a period with none as zero.

    The length of the range decides the size of a period: up to 48 hours it is an hour,
    up to 90 days a day, and beyond that a month.
    """
    effective_end = end or timezone.now()
    granularity, trunc_fn = _pick_granularity(start, effective_end)
    use_hourly = granularity == TimeGranularity.HOUR

    base_queryset = (
        StoredDetection.objects.of_species(species).in_period(start, end).approved().with_min_confidence(min_confidence)
    )
    detections_grouped_by_period = {
        _period_start(row["period_start"], use_hourly): row for row in _group_by_time_period(base_queryset, trunc_fn)
    }

    local_end = timezone.localtime(effective_end)

    if not start:
        rows = sorted(
            [
                {"day": period_start.isoformat(), "count": row["count"]}
                for period_start, row in detections_grouped_by_period.items()
            ],
            key=lambda row: row["day"],
        )
        return rows, granularity

    local_start = timezone.localtime(start)
    if granularity == TimeGranularity.MONTH:
        rows = _complete_month_series(detections_grouped_by_period, local_start, local_end)
    else:
        rows = _complete_bounded_series(detections_grouped_by_period, local_start, local_end, use_hourly)
    return rows, granularity


def species_detections_by_hour_of_day(
    species: Species,
    start: datetime | None,
    end: datetime | None,
    min_confidence: float | None = None,
) -> list[int]:
    """
    At what time of day the species is most active. Every date in the period is added
    together, so what comes back is 24 counts, one per hour of the clock.
    """
    hourly = [0] * 24
    base_queryset = (
        StoredDetection.objects.of_species(species).in_period(start, end).approved().with_min_confidence(min_confidence)
    )
    for row in _by_hour_of_day(base_queryset):
        hourly[row["hour"]] = row["count"]
    return hourly


def species_detections_by_date_and_hour(
    species: Species,
    start: datetime | None,
    end: datetime | None,
    min_confidence: float | None = None,
) -> tuple[list[dict], list[str], TimeGranularity]:
    """
    On which days and at which hours the detections happened, split by both at once. Made
    for a heatmap, with the date on one axis and the hour of day on the other.
    """
    end = end or timezone.now()
    use_daily = bool(start and (end - start).total_seconds() <= 90 * 24 * 3600)
    granularity = TimeGranularity.DAY if use_daily else TimeGranularity.MONTH
    trunc_fn = TruncDay if use_daily else TruncMonth

    local_end = timezone.localtime(end)
    day_start = timezone.localtime(start).replace(hour=0, minute=0, second=0, microsecond=0) if start else None
    day_end = local_end.replace(hour=23, minute=59, second=59, microsecond=999999)

    base_queryset = (
        StoredDetection.objects.of_species(species)
        .in_period(day_start, day_end)
        .approved()
        .with_min_confidence(min_confidence)
    )
    cells = [
        {"x": row["period_start"].date().isoformat(), "y": row["hour"], "v": row["count"]}
        for row in _by_heatmap_cell(base_queryset, trunc_fn)
    ]
    x_labels = _date_axis_labels(start, local_end, use_daily, cells)
    return cells, x_labels, granularity


def detections_by_species_hourly(
    min_confidence: float | None = None,
    lang: str = "en",
    top_species_count: int = 5,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict]:
    """
    What was heard in each hour of the period, the last 24 hours by default.

    Every hour comes back with its total, the busiest few species in full (names and
    image), and species_counts, which holds the count of every species that hour without
    the extra detail.
    """
    effective_end = end or timezone.now()
    effective_start = start or (effective_end - timedelta(hours=24))
    hours_in_period = max(1, round((effective_end - effective_start) / timedelta(hours=1)))

    per_species = (
        StoredDetection.objects.excluding_blacklisted()
        .in_period(effective_start, effective_end)
        .approved()
        .with_min_confidence(min_confidence)
        .annotate(hour=TruncHour("recorded_at"))
        .values("hour", "species_id")
        .annotate(detection_count=Count("id"))
    )

    by_hour: dict[datetime, list[dict]] = {}
    for row in per_species:
        by_hour.setdefault(row["hour"], []).append({"species_id": row["species_id"], "count": row["detection_count"]})

    all_species_ids = {entry["species_id"] for entries in by_hour.values() for entry in entries}
    species_map: dict[int, Species] = {}
    for detected_species in DetectedSpecies.objects.filter(id__in=all_species_ids):
        species = detected_species.to_entity()
        if species is not None:
            species_map[detected_species.id] = species

    first_hour = effective_start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    result = []
    for index in range(hours_in_period):
        hour_dt = first_hour + timedelta(hours=index)
        entries = sorted(by_hour.get(hour_dt, []), key=lambda entry: entry["count"], reverse=True)
        top_species = []
        for entry in entries[:top_species_count]:
            species = species_map.get(entry["species_id"])
            if species:
                top_species.append(
                    {
                        "scientific_name": species.scientific_name,
                        "common_name": species.common_name(lang),
                        "image_url": species.image_url,
                        "count": entry["count"],
                    }
                )
        species_counts = {
            species_map[entry["species_id"]].scientific_name: entry["count"]
            for entry in entries
            if entry["species_id"] in species_map
        }
        result.append(
            {
                "hour": hour_dt.isoformat(),
                "count": sum(entry["count"] for entry in entries),
                "top_species": top_species,
                "species_counts": species_counts,
            }
        )
    return result


def species_by_hour_of_day(
    species_list: list[Species],
    lang: str,
    start: datetime | None,
    end: datetime | None,
    min_confidence: float | None = None,
) -> dict:
    """
    Which species turn up at which hours of the day. Every date in the period is added
    together, so each species comes back with 24 counts, one per hour of the clock.

    Only the species asked for are returned, and in that order, minus any that are
    blacklisted or have never been heard here. The number of days in the period comes
    along too, so the caller can work out daily averages.
    """
    requested_names = [species.scientific_name for species in species_list]
    species_id_by_name = dict(
        DetectedSpecies.objects.filter(scientific_name__in=requested_names)
        .exclude(override__blacklisted=True)
        .values_list("scientific_name", "id")
    )

    base_queryset = (
        StoredDetection.objects.excluding_blacklisted()
        .in_period(start, end)
        .approved()
        .with_min_confidence(min_confidence)
        .filter(species_id__in=species_id_by_name.values())
    )
    per_species_hour = (
        base_queryset.annotate(hour=ExtractHour("recorded_at"))
        .values("species_id", "hour")
        .annotate(detection_count=Count("id"))
    )

    hour_counts_by_species_id: dict[int, list[int]] = {}
    for row in per_species_hour:
        hour_counts = hour_counts_by_species_id.setdefault(row["species_id"], [0] * 24)
        hour_counts[row["hour"]] += row["detection_count"]

    entries: list[dict] = []
    for species in species_list:
        species_id = species_id_by_name.get(species.scientific_name)
        if species_id is None:
            continue
        hour_counts = hour_counts_by_species_id.get(species_id, [0] * 24)
        entries.append(
            {
                "scientific_name": species.scientific_name,
                "common_name": species.common_name(lang),
                "image_url": species.image_url,
                "total": sum(hour_counts),
                "hours": hour_counts,
            }
        )

    return {"species": entries, "days": _period_days(base_queryset, start, end)}


def multi_species_timelines(
    species_list: list[Species],
    lang: str,
    start: datetime | None,
    end: datetime | None,
    min_confidence: float | None = None,
) -> tuple[list[dict], TimeGranularity]:
    """
    One timeline per species, skipping any that are blacklisted or have never been heard
    here.
    """
    requested_names = [species.scientific_name for species in species_list]
    visible_names = set(
        DetectedSpecies.objects.filter(scientific_name__in=requested_names)
        .exclude(override__blacklisted=True)
        .values_list("scientific_name", flat=True)
    )

    series = []
    granularity = TimeGranularity.DAY
    visible_species = [species for species in species_list if species.scientific_name in visible_names]
    for species in visible_species:
        data, granularity = species_detections_over_time(species, start, end, min_confidence)
        series.append(
            {
                "scientific_name": species.scientific_name,
                "common_name": species.common_name(lang),
                "data": data,
            }
        )
    return series, granularity


def species_detections_by_day_yearly(
    species: Species,
    min_confidence: float | None = None,
) -> dict[str, int]:
    """
    Detections per day over the past year, keyed by ISO date. Unlike the series builders
    above, a day with nothing heard is left out rather than set to zero.
    """
    since = timezone.now() - timedelta(days=364)
    queryset = (
        StoredDetection.objects.of_species(species)
        .in_period(since, None)
        .approved()
        .with_min_confidence(min_confidence)
    )
    rows = queryset.annotate(day=TruncDay("recorded_at")).values("day").annotate(count=Count("id")).order_by("day")
    return {row["day"].date().isoformat(): row["count"] for row in rows}


def _group_by_time_period(
    queryset: QuerySet, trunc_fn: type[TruncHour] | type[TruncDay] | type[TruncMonth]
) -> QuerySet:
    return cast(
        QuerySet,
        queryset.annotate(period_start=trunc_fn("recorded_at")).values("period_start").annotate(count=Count("id")),
    )


def _period_days(queryset: QuerySet, start: datetime | None, end: datetime | None) -> int:
    """
    How many days the period covers, which is what daily averages divide by.

    With no start given the period begins at the oldest detection, and with no detections
    either it counts as a single day.
    """
    effective_end = end or timezone.now()
    effective_start = start or queryset.aggregate(first_recorded_at=Min("recorded_at"))["first_recorded_at"]
    if effective_start is None:
        return 1
    return max(1, math.ceil((effective_end - effective_start) / timedelta(days=1)))


def _by_hour_of_day(queryset: QuerySet) -> QuerySet:
    return cast(
        QuerySet,
        queryset.annotate(hour=ExtractHour("recorded_at")).values("hour").annotate(count=Count("id")),
    )


def _by_heatmap_cell(queryset: QuerySet, trunc_fn: type[TruncHour] | type[TruncDay] | type[TruncMonth]) -> QuerySet:
    return cast(
        QuerySet,
        queryset.annotate(period_start=trunc_fn("recorded_at"), hour=ExtractHour("recorded_at"))
        .values("period_start", "hour")
        .annotate(count=Count("id")),
    )


def _period_start(dt: datetime, use_hourly: bool) -> datetime:
    """
    Move dt back to the start of its hour, or of its day when use_hourly is False.

    >>> _period_start(datetime(2024, 6, 15, 14, 37, 22), use_hourly=True)
    datetime.datetime(2024, 6, 15, 14, 0)
    >>> _period_start(datetime(2024, 6, 15, 14, 37, 22), use_hourly=False)
    datetime.datetime(2024, 6, 15, 0, 0)
    """
    if use_hourly:
        return dt.replace(minute=0, second=0, microsecond=0)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _month_labels(since_date: date, until_date: date) -> list[str]:
    """
    The first day of every month from since_date to until_date, both included, as ISO
    date strings.

    >>> _month_labels(date(2024, 11, 15), date(2025, 2, 3))
    ['2024-11-01', '2024-12-01', '2025-01-01', '2025-02-01']
    """
    labels, current = [], since_date.replace(day=1)
    while current <= until_date.replace(day=1):
        labels.append(current.isoformat())
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
    return labels


def _pick_granularity(
    start: datetime | None,
    effective_end: datetime,
) -> tuple[TimeGranularity, type[TruncHour] | type[TruncDay] | type[TruncMonth]]:
    if not start:
        return TimeGranularity.MONTH, TruncMonth
    total_secs = (effective_end - start).total_seconds()
    if total_secs <= 48 * 3600:
        return TimeGranularity.HOUR, TruncHour
    if total_secs <= 90 * 24 * 3600:
        return TimeGranularity.DAY, TruncDay
    return TimeGranularity.MONTH, TruncMonth


def _complete_month_series(
    by_period_start: dict[datetime, dict],
    local_start: datetime,
    local_end: datetime,
) -> list[dict]:
    """
    One entry per month from local_start to local_end, with the empty months set to zero.
    """
    by_year_and_month = {(period_start.year, period_start.month): row for period_start, row in by_period_start.items()}
    result = []
    for label in _month_labels(local_start.date(), local_end.date()):
        label_date = date.fromisoformat(label)
        period = by_year_and_month.get((label_date.year, label_date.month), {})
        result.append({"day": label, "count": period.get("count", 0)})
    return result


def _complete_bounded_series(
    by_period_start: dict[datetime, dict],
    local_start: datetime,
    local_end: datetime,
    use_hourly: bool,
) -> list[dict]:
    """
    One entry per hour or per day from local_start to local_end, with the empty ones set
    to zero.
    """
    step = timedelta(hours=1) if use_hourly else timedelta(days=1)
    first_period = _period_start(local_start, use_hourly)
    period_count = int((_period_start(local_end, use_hourly) - first_period) / step) + 1
    return [
        {
            "day": (first_period + step * index).isoformat(),
            "count": by_period_start.get(first_period + step * index, {}).get("count", 0),
        }
        for index in range(period_count)
    ]


def _date_axis_labels(
    start: datetime | None,
    local_end: datetime,
    use_daily: bool,
    cells: list[dict],
) -> list[str]:
    """
    The date labels for the heatmap's axis, in order. They are days or months depending
    on the range, and with no start given, just the dates that actually have data.
    """
    if not start:
        return sorted({cell["x"] for cell in cells})
    local_start = timezone.localtime(start)
    if use_daily:
        num_days = (local_end.date() - local_start.date()).days + 1
        return [(local_start.date() + timedelta(days=index)).isoformat() for index in range(num_days)]
    return _month_labels(local_start.date(), local_end.date())
