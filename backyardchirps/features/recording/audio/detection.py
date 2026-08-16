from dataclasses import dataclass
from dataclasses import field

from backyardchirps.features.species.entity import Species

# How far down the raw candidate list goes. It sits well below the detection floor
# (analysis_low_confidence) so the record shows everything BirdNET seriously weighed up,
# not just the species that made it through. Nothing here can create a detection.
RAW_CANDIDATE_FLOOR = 0.05


@dataclass
class AnalysisResult:
    species: Species
    confidence: float


@dataclass(frozen=True)
class RawCandidate:
    """
    One scored label from the model's raw output, left exactly as the model wrote it.
    Unlike AnalysisResult it is never resolved to a Species, which is what lets it hold
    labels the taxonomy does not know, such as non-bird sounds.
    """

    label: str
    confidence: float


@dataclass
class Analysis:
    """
    What came out of analyzing one clip. The results are the part the detection pipeline
    acts on. The raw candidates are only for the record, and include the non-bird labels
    and blacklisted species that the results leave out.
    """

    results: list[AnalysisResult]
    raw_candidates: list[RawCandidate] = field(default_factory=list)


def discard_non_birds(analysis_results: list[AnalysisResult]) -> list[AnalysisResult]:
    """
    BirdNET's taxonomy also covers insects, mammals, amphibians and reptiles, and none
    of those should become a detection. The caller still keeps the full raw candidate
    list for the record.
    """
    return [result for result in analysis_results if result.species.is_bird()]
