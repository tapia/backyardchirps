from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import StrEnum

from backyardchirps.features.species.entity import Species


class ValidationStatus(StrEnum):
    PENDING = "pending"
    AUTO_CONFIRMED = "auto_confirmed"
    HUMAN_CONFIRMED = "human_confirmed"


class SpeciesAlreadyIdentifiedException(Exception):
    pass


@dataclass(frozen=True)
class AnalysisCandidate:
    """
    One scored label from a detection's raw BirdNET output. `label` always holds the
    model's own text, while `species` is None for the labels our taxonomy does not know,
    such as non-bird sounds.
    """

    label: str
    confidence: float
    species: Species | None = None

    @classmethod
    def from_stored(cls, stored: dict) -> AnalysisCandidate:
        """
        Build a candidate from its stored {"label", "confidence"} JSON, resolving the
        label to a Species when the taxonomy knows it.
        """
        return cls(
            label=stored["label"],
            confidence=stored["confidence"],
            species=Species.from_scientific_name(stored["label"]),
        )


@dataclass(frozen=True)
class Detection:
    """
    One species heard at one moment with a confidence score, sometimes with a saved
    audio clip to go with it.
    """

    id: int
    species: Species
    recorded_at: datetime
    confidence: float
    clip_path: str | None
    clip_duration_seconds: float | None
    validation_status: ValidationStatus
    # What BirdNET originally said, saved at the moment a human overruled it. Stays None
    # until someone changes the species.
    original_species: Species | None = None
    original_confidence: float | None = None
    # How long the model took on the clip, and everything it heard there. Empty on
    # detections made before we started recording this.
    analysis_time_ms: int | None = None
    analysis_candidates: list[AnalysisCandidate] = field(default_factory=list)

    def is_pending_validation(self) -> bool:
        return self.validation_status == ValidationStatus.PENDING

    def reviewed_by_human(self) -> bool:
        return self.validation_status == ValidationStatus.HUMAN_CONFIRMED
