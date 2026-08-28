from datetime import datetime
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import NotFound
from rest_framework.exceptions import ParseError
from rest_framework.request import Request

from backyardchirps.features.overrides import queries as override_queries
from backyardchirps.features.species import queries as species_queries
from backyardchirps.features.species.entity import Species


def request_body(request: Request) -> dict[str, Any]:
    """
    The parsed request body, as an object.

    A JSON body can be an array as well as an object, so that is what DRF says
    request.data holds. Every endpoint here wants an object, and reading a key off an
    array is a client error rather than something to recover from, so this answers it
    with 400 instead of failing later on a missing attribute.
    """
    if not isinstance(request.data, dict):
        raise ParseError("Expected a JSON object.")
    return request.data


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


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is None:
        return None
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
