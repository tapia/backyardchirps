"""
Root URL configuration.

Every route points straight at the view that owns it, inside its own feature. There is no
central api package collecting them.
"""

from django.contrib import admin
from django.urls import path

from backyardchirps.features.analytics import views as analytics_views
from backyardchirps.features.auth import views as auth_views
from backyardchirps.features.detections import views as detections_views
from backyardchirps.features.overrides import views as overrides_views
from backyardchirps.features.region_packs import views as region_packs_views
from backyardchirps.features.server_status import views as server_status_views
from backyardchirps.features.settings import views as settings_views
from backyardchirps.features.setup import views as setup_views
from backyardchirps.features.species import views as species_views
from backyardchirps.features.updates import views as updates_views
from backyardchirps.features.weather import views as weather_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/me/", auth_views.me, name="api-auth-me"),
    path("api/auth/login/", auth_views.login_view, name="api-auth-login"),
    path("api/auth/logout/", auth_views.logout_view, name="api-auth-logout"),
    path("api/settings/", settings_views.app_settings, name="api-settings"),
    # The wizard is server-rendered: one URL per step, a POST to move on, and the step a
    # visitor is on is the URL they are at. The SPA asks setup_status whether to send
    # them here at all, and the settings page reuses audio_devices.
    #
    # audio-level is listed before the step route because "audio-level" would otherwise
    # match <slug:step> and be looked up as a step of the wizard.
    path("setup/", setup_views.wizard, name="setup"),
    path("setup/audio-level/", setup_views.audio_level, name="setup-audio-level"),
    path("setup/<slug:step>/", setup_views.wizard_step, name="setup-step"),
    path("api/setup/status/", setup_views.setup_status, name="api-setup-status"),
    # Packs are asked about by the wizard and by the settings page, so they are their own
    # feature rather than part of setup. Both reach the same view, which is what stops the
    # two disagreeing about which pack covers a point.
    path("api/region-packs/region-pack/", region_packs_views.region_pack, name="api-region-packs-region-pack"),
    path("api/region-packs/installed/", region_packs_views.installed_region_pack, name="api-region-packs-installed"),
    path("api/region-packs/install/", region_packs_views.install_region_pack, name="api-region-packs-install"),
    path(
        "api/region-packs/install/progress/",
        region_packs_views.install_progress,
        name="api-region-packs-install-progress",
    ),
    path("api/setup/audio-devices/", setup_views.audio_devices, name="api-setup-audio-devices"),
    path("api/server-status/", server_status_views.server_status, name="api-server-status"),
    path("api/updates/available/", updates_views.available_update, name="api-updates-available"),
    path("api/updates/apply/", updates_views.apply_update, name="api-updates-apply"),
    path("api/updates/progress/", updates_views.update_progress, name="api-updates-progress"),
    path("api/weather/current/", weather_views.current_weather, name="api-weather-current"),
    path(
        "api/detections/hourly/",
        analytics_views.count_detections_by_species_hourly,
        name="api-detections-hourly",
    ),
    path(
        "api/detections/by-hour-of-day/",
        analytics_views.detections_by_hour_of_day,
        name="api-detections-by-hour-of-day",
    ),
    path(
        "api/detections/timeline/",
        analytics_views.multi_species_timeline,
        name="api-detections-timeline",
    ),
    path("api/species/", species_views.species_list, name="api-species-list"),
    path(
        "api/species/detection-settings/",
        overrides_views.detection_settings_list,
        name="api-detection-settings-list",
    ),
    path(
        "api/species/<str:slug>/",
        species_views.species_detail,
        name="api-species-detail",
    ),
    path(
        "api/species/<str:slug>/detection-settings/",
        overrides_views.species_detection_settings,
        name="api-species-detection-settings",
    ),
    path(
        "api/species/<str:slug>/hourly/",
        analytics_views.species_hourly,
        name="api-species-hourly",
    ),
    path(
        "api/species/<str:slug>/heatmap/",
        analytics_views.species_heatmap,
        name="api-species-heatmap",
    ),
    path(
        "api/species/<str:slug>/yearly/",
        analytics_views.species_yearly,
        name="api-species-yearly",
    ),
    path(
        "api/species/<str:slug>/seasonality/",
        species_views.species_seasonality,
        name="api-species-seasonality",
    ),
    path(
        "api/species/<str:slug>/recordings/",
        species_views.species_recordings,
        name="api-species-recordings",
    ),
    path("api/taxonomy/search/", species_views.taxonomy_search, name="api-taxonomy-search"),
    path("api/detections/", detections_views.detections_list, name="api-detections-list"),
    path("api/detections/dubious/", detections_views.dubious_detections, name="api-dubious-detections"),
    path(
        "api/detections/dubious/count/",
        detections_views.dubious_detections_count,
        name="api-dubious-detections-count",
    ),
    path("api/detections/validate/", detections_views.validate_detections, name="api-validate-detections"),
    path(
        "api/detections/<int:pk>/validate/",
        detections_views.validate_detection,
        name="api-validate-detection",
    ),
    path(
        "api/detections/<int:pk>/",
        detections_views.detection_detail,
        name="api-detection-detail",
    ),
    path("api/clips/<path:filepath>", detections_views.serve_clip, name="api-serve-clip"),
    path(
        "species-data/<str:category>/<str:filename>",
        species_views.serve_species_asset,
        name="species-asset",
    ),
]
