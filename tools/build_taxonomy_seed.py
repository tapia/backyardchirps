"""
Cut the small taxonomy that ships in the repository out of the full BirdNET one.

  uv run --no-project python tools/build_taxonomy_seed.py [--source FILE] [--species-count N]

The full taxonomy is not tracked any more: it is the BirdNET API's output, committed
verbatim, and every refresh of it would add tens of megabytes to the history for good. A
station gets it from the backyardchirps-species-data package, and a checkout downloads it
with `manage.py update_species_data`.

What stays tracked is the seed this writes: a few hundred species, entries copied
unchanged, enough that a fresh clone boots and the test suite has real data to assert on.
Species() validates against whatever taxonomy is loaded, so the suite would fail loudly if
a name it uses were missing from here.

Entries are copied byte for byte rather than trimmed, so the seed is a real sample of the
upstream shape and not a hand-made imitation of it. Selection is deterministic: run this
against the same source twice and the two files are identical.

--no-project because nothing here needs the project environment, and the whole point of
the seed is that it exists before one can be used.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SEED_FILE = REPO_ROOT / "backyardchirps" / "species_data" / "taxonomy" / "birdnet_taxonomy.json"

# Where update_species_data writes the full taxonomy in a checkout, which is where this
# reads it from unless told otherwise.
DEFAULT_SOURCE = REPO_ROOT / "backyardchirps" / "species_data" / "generated" / "taxonomy" / "birdnet_taxonomy.json"

# Names the test suite spells out, so the seed has to carry them. The suite asserts on
# their common names, their eBird codes and their taxon group, meaning these entries also
# have to stay copies of the real ones.
REQUIRED_SPECIES = [
    "Turdus merula",
    "Turdus philomelos",
    "Erithacus rubecula",
    "Passer domesticus",
    # Not a bird. BirdNET's taxonomy covers insects too, and is_bird() is tested on it.
    "Acheta domesticus",
]

# Enough species that a search returns several results and every taxon group appears, and
# small enough that reading the file costs nothing.
DEFAULT_SPECIES_COUNT = 300


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="the full taxonomy to sample")
    parser.add_argument("--species-count", type=int, default=DEFAULT_SPECIES_COUNT)
    arguments = parser.parse_args()

    if not arguments.source.exists():
        sys.exit(
            f"No full taxonomy at {arguments.source}.\n"
            "Run `uv run python manage.py update_species_data` first, or pass --source."
        )

    with open(arguments.source, encoding="utf-8") as source_file:
        taxa = json.load(source_file)

    seed = _select(taxa, arguments.species_count)

    SEED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SEED_FILE, "w", encoding="utf-8") as seed_file:
        json.dump(seed, seed_file, ensure_ascii=False, indent=2)
        seed_file.write("\n")

    print(f"Wrote {len(seed)} species to {SEED_FILE} ({SEED_FILE.stat().st_size / 1_000_000:.1f} MB)")


def _select(taxa: list[dict], species_count: int) -> list[dict]:
    """
    The species the tests name, every Turdus, and then an even stride over the rest until
    the count is reached. The stride is what keeps every taxon group represented without
    naming any of them here.
    """
    by_scientific_name = {taxon["scientific_name"]: taxon for taxon in taxa}

    missing = [name for name in REQUIRED_SPECIES if name not in by_scientific_name]
    if missing:
        sys.exit(f"The source taxonomy does not have: {', '.join(missing)}")

    selected = {name: by_scientific_name[name] for name in REQUIRED_SPECIES}
    for taxon in taxa:
        if taxon["scientific_name"].startswith("Turdus "):
            selected[taxon["scientific_name"]] = taxon

    stride = max(1, len(taxa) // max(1, species_count - len(selected)))
    for taxon in taxa[::stride]:
        if len(selected) >= species_count:
            break
        selected[taxon["scientific_name"]] = taxon

    return sorted(selected.values(), key=lambda taxon: taxon["scientific_name"])


if __name__ == "__main__":
    main()
