from datetime import timedelta

from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from backyardchirps import settings
from backyardchirps.features.analytics import queries as analytics_repository
from backyardchirps.features.species.entity import Species
from backyardchirps.features.weather.astronomy import AstronomyService
from backyardchirps.features.weather.astronomy import serialize_astro_times
from backyardchirps.shared.http import _parse_dt
from backyardchirps.shared.http import _resolve_confidence_level
from backyardchirps.shared.http import get_detected_species_or_404

_astronomy = AstronomyService()


@api_view(["GET"])
def count_detections_by_species_hourly(request):
    min_confidence = _resolve_confidence_level(request)
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    offset = int(request.GET.get("offset", "0"))
    now = timezone.now()
    end = now - timedelta(hours=24 * offset) if offset > 0 else now
    start = end - timedelta(hours=24)
    start_date = timezone.localtime(start).date()
    end_date = timezone.localtime(end).date()
    astro_dates = [start_date] if start_date == end_date else [start_date, end_date]
    return Response(
        {
            "hours": analytics_repository.detections_by_species_hourly(min_confidence, lang, start=start, end=end),
            "astro": serialize_astro_times([_astronomy.get_for_date(d) for d in astro_dates]),
        }
    )


@api_view(["GET"])
def detections_by_hour_of_day(request):
    min_confidence = _resolve_confidence_level(request)
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    start = _parse_dt(request.GET.get("start"))
    end = _parse_dt(request.GET.get("end"))
    slugs = request.GET.getlist("species")
    species_list = [species for species in (Species.from_slug(slug) for slug in slugs) if species is not None]
    return Response(analytics_repository.species_by_hour_of_day(species_list, lang, start, end, min_confidence))


@api_view(["GET"])
def species_hourly(request, slug):
    start, end = _parse_dt(request.GET.get("start")), _parse_dt(request.GET.get("end"))
    min_confidence = _resolve_confidence_level(request)
    species = get_detected_species_or_404(slug)

    hourly = analytics_repository.species_detections_by_hour_of_day(species, start, end, min_confidence)
    return Response({"hourly": hourly})


@api_view(["GET"])
def species_heatmap(request, slug):
    start, end = _parse_dt(request.GET.get("start")), _parse_dt(request.GET.get("end"))
    min_confidence = _resolve_confidence_level(request)
    species = get_detected_species_or_404(slug)

    cells, x_labels, granularity = analytics_repository.species_detections_by_date_and_hour(
        species, start, end, min_confidence
    )

    return Response({"heatmap": cells, "x_labels": x_labels, "granularity": granularity.value})


@api_view(["GET"])
def species_yearly(request, slug):
    min_confidence = _resolve_confidence_level(request)
    species = get_detected_species_or_404(slug)
    daily = analytics_repository.species_detections_by_day_yearly(species, min_confidence)
    return Response({"daily": daily})


@api_view(["GET"])
def multi_species_timeline(request):
    slugs = request.GET.getlist("species")
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    start, end = _parse_dt(request.GET.get("start")), _parse_dt(request.GET.get("end"))
    min_confidence = _resolve_confidence_level(request)

    species_list = [species for species in (Species.from_slug(slug) for slug in slugs) if species is not None]
    series, granularity = analytics_repository.multi_species_timelines(species_list, lang, start, end, min_confidence)

    return Response({"series": series, "granularity": granularity.value})
