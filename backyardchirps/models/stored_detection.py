from datetime import datetime

from django.db import models

from backyardchirps.features.detections.entity import AnalysisCandidate
from backyardchirps.features.detections.entity import Detection
from backyardchirps.features.detections.entity import ValidationStatus
from backyardchirps.features.recording.audio.clip import AudioClip
from backyardchirps.features.species.entity import Species
from backyardchirps.models.detected_species import DetectedSpecies


def validation_status_choices() -> list[tuple[str, str]]:
    """
    Passed as a callable to StoredDetection.validation_status, so that adding a status to
    the enum does not need a migration.
    """
    return [(status.value, status.value) for status in ValidationStatus]


class StoredDetectionQuerySet(models.QuerySet["StoredDetection"]):
    """
    Chainable filters for detection queries.

    A method given None, or an empty list, filters nothing at all. That way an optional
    request parameter can be passed straight in without checking it first.
    """

    def of_species(self, species: Species) -> "StoredDetectionQuerySet":
        return self.filter(species__scientific_name=species.scientific_name)

    def in_period(self, start: datetime | None, end: datetime | None) -> "StoredDetectionQuerySet":
        queryset = self
        if start:
            queryset = queryset.filter(recorded_at__gte=start)
        if end:
            queryset = queryset.filter(recorded_at__lte=end)
        return queryset

    def approved(self) -> "StoredDetectionQuerySet":
        """
        What the site shows: everything except the detections waiting for review.
        """
        return self.filter(validation_status__in=ValidationStatus.approved())

    def with_min_confidence(self, min_confidence: float | None) -> "StoredDetectionQuerySet":
        if min_confidence is None:
            return self
        return self.filter(confidence__gte=min_confidence)

    def excluding_blacklisted(self) -> "StoredDetectionQuerySet":
        return self.exclude(species__override__blacklisted=True)

    def with_saved_clip(self) -> "StoredDetectionQuerySet":
        return self.exclude(clip_path__isnull=True).exclude(clip_path="")

    def recorded_with(self, recorded_at: datetime) -> "StoredDetectionQuerySet":
        """
        Every row that came from the same clip as this moment.
        """
        return self.filter(recorded_at=recorded_at)


class StoredDetection(models.Model):
    """
    How a detection is stored. The detections feature's queries map it to and from the
    Detection entity.
    """

    objects = StoredDetectionQuerySet.as_manager()

    # When the audio was captured. Rows sharing a recorded_at all came from the same clip.
    recorded_at = models.DateTimeField(db_index=True)

    species = models.ForeignKey(DetectedSpecies, on_delete=models.CASCADE, related_name="detections")
    confidence = models.FloatField()
    clip_path = models.CharField(max_length=500, null=True, blank=True)
    clip_duration_seconds = models.FloatField(null=True, blank=True)
    validation_status = models.CharField(
        max_length=20,
        choices=validation_status_choices,
        default=ValidationStatus.AUTO_CONFIRMED,
    )
    # What BirdNET said, saved at the moment a human validation overwrote `species` and
    # `confidence`. Null until someone overrules the machine.
    original_species = models.ForeignKey(
        DetectedSpecies,
        on_delete=models.SET_NULL,
        related_name="original_detections",
        null=True,
        blank=True,
    )
    original_confidence = models.FloatField(null=True, blank=True)
    # How long the model took on the clip, in milliseconds, and everything it heard
    # there: {"label", "confidence"} for each candidate above the floor that the location
    # filter let through, non-bird sounds and blacklisted species included. Both are
    # empty on rows recorded before we started saving them.
    analysis_time_ms = models.IntegerField(null=True, blank=True)
    analysis_candidates = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "birds_recorder_detection"
        ordering = ["-recorded_at"]  # noqa: RUF012

    def __str__(self) -> str:
        return f"{self.species}: {self.confidence:.0%} at {self.recorded_at}"

    def confirm(self, reassigned_species: Species | None = None) -> None:
        """
        Confirm this detection, changing its species first if asked. Confidence becomes
        1.0, since a human is now sure.

        The original_* fields are filled the first time anyone confirms it, and never
        touched again. They therefore always hold what BirdNET said, not what the
        previous reviewer decided.
        """
        update_fields = ["confidence", "validation_status"]
        if self.original_species_id is None:
            self.original_species_id = self.species_id
            self.original_confidence = self.confidence
            update_fields += ["original_species", "original_confidence"]
        if reassigned_species is not None:
            self.species, _ = DetectedSpecies.objects.get_or_create(scientific_name=reassigned_species.scientific_name)
            update_fields.append("species")
        self.confidence = 1.0
        self.validation_status = ValidationStatus.HUMAN_CONFIRMED
        self.save(update_fields=update_fields)

    def discard(self) -> None:
        """
        Delete this detection's saved clip, if it has one, and then the row.
        """
        AudioClip.delete_clip(self.clip_path)
        self.delete()

    def to_entity(self) -> Detection | None:
        """
        None when the row's species has since left the taxonomy.
        """
        species = self.species.to_entity()
        if species is None:
            return None
        return Detection(
            id=self.id,
            species=species,
            recorded_at=self.recorded_at,
            confidence=self.confidence,
            clip_path=self.clip_path,
            clip_duration_seconds=self.clip_duration_seconds,
            validation_status=ValidationStatus(self.validation_status),
            original_species=self._original_species(),
            original_confidence=self.original_confidence,
            analysis_time_ms=self.analysis_time_ms,
            analysis_candidates=self._analysis_candidates(),
        )

    def _original_species(self) -> Species | None:
        original = self.original_species
        if original is None:
            return None
        return original.to_entity()

    def _analysis_candidates(self) -> list[AnalysisCandidate]:
        return [AnalysisCandidate.from_stored(candidate) for candidate in (self.analysis_candidates or [])]
