from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.weather.logic import WeatherService
from backyardchirps.features.weather.logic import serialize_weather_reading

_weather_service = WeatherService()


@api_view(["GET"])
@permission_classes([AllowAny])
def current_weather(request: Request) -> Response:
    """
    The weather at the station, plus the local time there.
    """
    temperature_unit = Settings.get(SettingsKey.WEATHER_TEMPERATURE_UNIT)
    wind_speed_unit = Settings.get(SettingsKey.WEATHER_WIND_SPEED_UNIT)
    reading = _weather_service.get_current()
    return Response(
        {
            **serialize_weather_reading(reading, temperature_unit, wind_speed_unit),
            "local_time": timezone.localtime(timezone.now()).isoformat(),
        }
    )
