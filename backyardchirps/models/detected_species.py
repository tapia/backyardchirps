from django.db import models

from backyardchirps.features.species.entity import Species


class DetectedSpecies(models.Model):
    """
    A species heard at least once at this station. Storage only: everything that comes
    from the taxonomy lives on the Species entity instead.
    """

    scientific_name = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = "birds_recorder_species"
        verbose_name_plural = "detected species"

    def __str__(self) -> str:
        return self.scientific_name

    def to_entity(self) -> Species | None:
        """
        None when a taxonomy update has dropped a name that old rows still carry.
        """
        return Species.from_scientific_name(self.scientific_name)
