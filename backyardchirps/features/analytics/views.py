from datetime import timedelta

from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps import settings
from backyardchirps.features.analytics import queries as analytics_queries
from backyardchirps.features.species.entity import Species
from backyardchirps.features.weather.astronomy import get_for_date as get_astro_times
from backyardchirps.features.weather.astronomy import serialize_astro_times
from backyardchirps.shared.http import get_detected_species_or_404
from backyardchirps.shared.http import parse_dt


@api_view(["GET"])
@permission_classes([AllowAny])
def count_detections_by_species_hourly(request: Request) -> Response:
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
            "hours": analytics_queries.detections_by_species_hourly(lang, start=start, end=end),
            "astro": serialize_astro_times([get_astro_times(astro_date) for astro_date in astro_dates]),
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def detections_by_hour_of_day(request: Request) -> Response:
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    start = parse_dt(request.GET.get("start"))
    end = parse_dt(request.GET.get("end"))
    slugs = request.GET.getlist("species")
    species_list = [species for species in (Species.from_slug(slug) for slug in slugs) if species is not None]
    return Response(analytics_queries.species_by_hour_of_day(species_list, lang, start, end))


@api_view(["GET"])
@permission_classes([AllowAny])
def species_hourly(request: Request, slug: str) -> Response:
    start, end = parse_dt(request.GET.get("start")), parse_dt(request.GET.get("end"))
    species = get_detected_species_or_404(slug)

    hourly = analytics_queries.species_detections_by_hour_of_day(species, start, end)
    return Response({"hourly": hourly})


@api_view(["GET"])
@permission_classes([AllowAny])
def species_heatmap(request: Request, slug: str) -> Response:
    start, end = parse_dt(request.GET.get("start")), parse_dt(request.GET.get("end"))
    species = get_detected_species_or_404(slug)

    cells, x_labels, granularity = analytics_queries.species_detections_by_date_and_hour(species, start, end)

    return Response({"heatmap": cells, "x_labels": x_labels, "granularity": granularity.value})


@api_view(["GET"])
@permission_classes([AllowAny])
def species_yearly(request: Request, slug: str) -> Response:
    species = get_detected_species_or_404(slug)
    daily = analytics_queries.species_detections_by_day_yearly(species)
    return Response({"daily": daily})


@api_view(["GET"])
@permission_classes([AllowAny])
def multi_species_timeline(request: Request) -> Response:
    slugs = request.GET.getlist("species")
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    start, end = parse_dt(request.GET.get("start")), parse_dt(request.GET.get("end"))

    species_list = [species for species in (Species.from_slug(slug) for slug in slugs) if species is not None]
    series, granularity = analytics_queries.multi_species_timelines(species_list, lang, start, end)

    return Response({"series": series, "granularity": granularity.value})
