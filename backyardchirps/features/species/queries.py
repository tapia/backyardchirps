from backyardchirps.features.species.entity import Species
from backyardchirps.models.detected_species import DetectedSpecies


def has_been_detected(species: Species) -> bool:
    return DetectedSpecies.objects.filter(scientific_name=species.scientific_name).exists()
