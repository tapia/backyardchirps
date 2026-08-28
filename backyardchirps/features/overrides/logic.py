from typing import cast

from backyardchirps.features.detections import queries as detection_queries
from backyardchirps.features.overrides import queries
from backyardchirps.features.overrides.entity import SpeciesOverride
from backyardchirps.features.settings.logic import Settings
from backyardchirps.features.settings.logic import SettingsKey
from backyardchirps.features.species.entity import Species


def set_override(species: Species, auto_confirm_threshold: float | None, blacklisted: bool) -> SpeciesOverride | None:
    """
    Create or replace the species' override. An override that customizes nothing is
    deleted instead, and None comes back.
    """
    if not blacklisted and auto_confirm_threshold is None:
        clear_override(species)
        return None

    old_bar = _effective_bar(queries.get(species))
    override = queries.upsert(species, auto_confirm_threshold, blacklisted)
    _clear_queue_if_lowered(species, old_bar, _effective_bar(override))
    return override


def clear_override(species: Species) -> None:
    """
    Put the species back on the global defaults. Should that lower its auto-confirm bar,
    the detections that were only waiting on the old bar are confirmed.
    """
    old_bar = _effective_bar(queries.get(species))
    queries.delete(species)
    _clear_queue_if_lowered(species, old_bar, _global_bar())


def _clear_queue_if_lowered(species: Species, old_bar: float, new_bar: float) -> None:
    if new_bar < old_bar:
        detection_queries.auto_confirm_pending_above(species, new_bar)


def _effective_bar(override: SpeciesOverride | None) -> float:
    if override is not None and override.auto_confirm_threshold is not None:
        return override.auto_confirm_threshold
    return _global_bar()


def _global_bar() -> float:
    return cast(float, Settings.get(SettingsKey.ANALYSIS_AUTO_CONFIRM_CONFIDENCE))
