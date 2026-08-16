import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    """
    The ground a pack covers, in degrees. West and south are the lower corner.
    """

    west: float
    south: float
    east: float
    north: float

    @classmethod
    def from_index(cls, values: dict[str, Any]) -> "BoundingBox":
        return cls(
            west=float(values["west"]),
            south=float(values["south"]),
            east=float(values["east"]),
            north=float(values["north"]),
        )

    def contains(self, latitude: float, longitude: float) -> bool:
        return self.west <= longitude <= self.east and self.south <= latitude <= self.north

    def distance_from(self, latitude: float, longitude: float) -> float:
        """
        Roughly how far the point is from the nearest edge, in kilometres, and zero inside.

        Only ever used to sort the misses, so that "no pack covers you, the nearest is
        this one" names the one a reader would agree is nearest. Longitude degrees are
        narrowed by the latitude, without which a point in northern Europe would be told
        the nearest pack is the wrong one.
        """
        if self.contains(latitude, longitude):
            return 0.0

        degrees_north = max(self.south - latitude, 0.0, latitude - self.north)
        degrees_east = max(self.west - longitude, 0.0, longitude - self.east)
        kilometres_per_degree = 111.0
        narrowing = math.cos(math.radians(latitude))
        return math.hypot(degrees_north, degrees_east * narrowing) * kilometres_per_degree


@dataclass(frozen=True)
class RegionPack:
    """
    A pack as the index describes it, which is everything needed to offer it and to
    download it. A pack on disk is the same thing unpacked.
    """

    id: str
    names: dict[str, str]
    bbox: BoundingBox
    version: str
    species_count: int
    url: str
    sha256: str
    size_bytes: int

    @classmethod
    def from_index(cls, entry: dict[str, Any]) -> "RegionPack":
        """
        Read one index entry. Raises KeyError or ValueError on anything malformed, so a
        broken index is refused rather than half understood.
        """
        return cls(
            id=str(entry["id"]),
            names={str(code): str(name) for code, name in dict(entry["names"]).items()},
            bbox=BoundingBox.from_index(entry["bbox"]),
            version=str(entry["version"]),
            species_count=int(entry["species_count"]),
            url=str(entry["url"]),
            sha256=str(entry["sha256"]),
            size_bytes=int(entry["size_bytes"]),
        )

    def name_in(self, language_code: str) -> str:
        """
        The pack's name in this language, falling back to English and then to the id, so
        a pack added with only one name still has something to show.
        """
        return self.names.get(language_code) or self.names.get("en") or self.id


@dataclass(frozen=True)
class RegionPackChoice:
    """
    What to offer a station at some coordinates: the pack covering it, or the nearest one
    when none does.

    Both cases are answered the same way on purpose. "No pack covers you, the nearest is
    the Iberian Peninsula, 400km away" tells its reader far more than an empty list, and
    it is what turns a miss into a request for a pack that should exist.
    """

    region_pack: RegionPack | None
    covers: bool
    distance_km: float | None
