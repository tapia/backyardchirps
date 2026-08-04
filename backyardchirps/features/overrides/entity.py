from __future__ import annotations

from dataclasses import dataclass

from backyardchirps.features.species.entity import Species


@dataclass(frozen=True)
class SpeciesOverride:
    """
    An admin customization applied to one species.

    A blacklisted species behaves as if it had never been heard. New detections are
    thrown away before they are stored, and the old ones are hidden everywhere until the
    species leaves the blacklist. The other species in the same clip are unaffected.

    An auto_confirm_threshold replaces the global auto-confirm bar for this species
    alone, which changes how confident a detection must be to skip the review queue.
    """

    species: Species
    auto_confirm_threshold: float | None
    blacklisted: bool
