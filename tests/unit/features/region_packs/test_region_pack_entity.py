"""
Reading the packs index, and deciding which pack covers a point.
"""

import pytest

from backyardchirps.features.region_packs.entity import BoundingBox
from backyardchirps.features.region_packs.entity import RegionPack

IBERIA = {
    "id": "iberian-peninsula",
    "names": {"en": "Iberian Peninsula", "es": "Península ibérica"},
    "bbox": {"west": -10.8, "south": 34.2, "east": 5.4, "north": 44.9},
    "version": "2026-08-16",
    "species_count": 312,
    "url": "https://example.com/iberian-peninsula-2026-08-16.tar.zst",
    "sha256": "abc",
    "size_bytes": 123,
}


class TestReadingAnIndexEntry:
    def test_reads_everything_a_download_needs(self) -> None:
        pack = RegionPack.from_index(IBERIA)

        assert pack.id == "iberian-peninsula"
        assert pack.url.endswith(".tar.zst")
        assert pack.sha256 == "abc"
        assert pack.size_bytes == 123
        assert pack.bbox.west == -10.8

    @pytest.mark.parametrize("missing", ["id", "bbox", "url", "sha256", "size_bytes"])
    def test_refuses_an_entry_missing_anything_it_needs(self, missing: str) -> None:
        # Refused rather than half understood, so a broken index costs that one pack.
        entry = {key: value for key, value in IBERIA.items() if key != missing}

        with pytest.raises((KeyError, TypeError, ValueError)):
            RegionPack.from_index(entry)

    def test_names_the_pack_in_the_readers_language(self) -> None:
        pack = RegionPack.from_index(IBERIA)

        assert pack.name_in("es") == "Península ibérica"
        assert pack.name_in("en") == "Iberian Peninsula"

    def test_falls_back_to_english_then_to_the_id(self) -> None:
        english_only = RegionPack.from_index({**IBERIA, "names": {"en": "Iberian Peninsula"}})
        nameless = RegionPack.from_index({**IBERIA, "names": {}})

        assert english_only.name_in("es") == "Iberian Peninsula"
        assert nameless.name_in("es") == "iberian-peninsula"


class TestWhichPackCoversAPoint:
    def test_a_point_inside_the_box_is_covered(self) -> None:
        box = BoundingBox(west=-10.8, south=34.2, east=5.4, north=44.9)

        assert box.contains(40.4, -3.7) is True
        assert box.distance_from(40.4, -3.7) == 0.0

    def test_the_edges_count_as_inside(self) -> None:
        # A station on a boundary has to belong to one of them rather than to neither.
        box = BoundingBox(west=-10.8, south=34.2, east=5.4, north=44.9)

        assert box.contains(34.2, -10.8) is True
        assert box.contains(44.9, 5.4) is True

    def test_a_point_outside_is_not_covered_and_has_a_distance(self) -> None:
        box = BoundingBox(west=-10.8, south=34.2, east=5.4, north=44.9)

        assert box.contains(52.4, 4.9) is False
        assert box.distance_from(52.4, 4.9) > 0.0

    def test_distance_narrows_longitude_with_latitude(self) -> None:
        """
        Ten degrees of longitude is a much shorter distance in Norway than at the equator.
        Without this, a northern station would be told the nearest pack is the wrong one.
        """
        box = BoundingBox(west=-10.0, south=0.0, east=0.0, north=60.0)

        near_the_equator = box.distance_from(1.0, 10.0)
        far_north = box.distance_from(59.0, 10.0)

        assert far_north < near_the_equator

    def test_the_nearest_of_two_boxes_is_the_nearer_one(self) -> None:
        iberia = BoundingBox(west=-10.8, south=34.2, east=5.4, north=44.9)
        canaries = BoundingBox(west=-18.6, south=27.4, east=-13.1, north=29.8)

        # A point just south of Iberia, well north of the Canaries.
        assert iberia.distance_from(33.0, -6.0) < canaries.distance_from(33.0, -6.0)
