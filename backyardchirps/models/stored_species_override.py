from django.db import models

from backyardchirps.features.overrides.entity import SpeciesOverride
from backyardchirps.models.detected_species import DetectedSpecies


class StoredSpeciesOverride(models.Model):
    """
    How a species customization is stored. The overrides feature's queries map it to and
    from the SpeciesOverride entity.
    """

    species = models.OneToOneField(DetectedSpecies, on_delete=models.CASCADE, related_name="override")
    auto_confirm_threshold = models.FloatField(null=True, blank=True)
    blacklisted = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "species override"

    def __str__(self) -> str:
        return self.species.scientific_name

    def to_entity(self) -> SpeciesOverride | None:
        """
        None when the row's species has since left the taxonomy.
        """
        species = self.species.to_entity()
        if species is None:
            return None
        return SpeciesOverride(
            species=species,
            auto_confirm_threshold=self.auto_confirm_threshold,
            blacklisted=self.blacklisted,
        )
