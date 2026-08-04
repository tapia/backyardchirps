from datetime import datetime
from enum import Enum
from typing import cast

from django.http import HttpRequest
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import NotFound

from backyardchirps.features.overrides import queries as override_queries
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.species import queries as species_queries
from backyardchirps.features.species.entity import Species


def get_species_or_404(slug: str) -> Species:
    """
    Turn a species slug from a URL into a Species, raising 404 for an unknown slug.
    """
    species = Species.from_slug(slug)
    if species is None:
        raise NotFound() from None
    return species


def get_detected_species_or_404(slug: str) -> Species:
    """
    Like get_species_or_404, but also 404s unless the species has been heard here.
    Blacklisted species 404 too, since they look like they never were.
    """
    species = get_species_or_404(slug)
    if override_queries.is_blacklisted(species):
        raise NotFound() from None
    if not species_queries.has_been_detected(species):
        raise NotFound() from None
    return species


class ConfidenceLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


def _resolve_confidence_level(request: HttpRequest) -> float | None:
    """
    Turn the 'min_confidence' query parameter, one of low, medium or high, into the
    threshold it stands for. Anything else is treated as high. "low" means no threshold
    at all, so it returns None.

    The thresholds are read from AppSetting on every request, so changing one takes
    effect at once.
    """
    raw = request.GET.get("min_confidence", ConfidenceLevel.HIGH.value)
    try:
        level = ConfidenceLevel(raw)
    except ValueError:
        level = ConfidenceLevel.HIGH
    if level == ConfidenceLevel.LOW:
        return None
    settings_key = (
        SettingsKey.ANALYSIS_MEDIUM_CONFIDENCE
        if level == ConfidenceLevel.MEDIUM
        else SettingsKey.ANALYSIS_HIGH_CONFIDENCE
    )
    return cast(float, Settings.get(settings_key))
