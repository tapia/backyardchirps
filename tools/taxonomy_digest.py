"""
Download the BirdNET taxonomy and print the digest the species-data package would carry.

  uv run --no-project python tools/taxonomy_digest.py [--out PATH]

The nightly job uses this to answer one question: is upstream serving something other than
what the repository already offers? DATA_VERSION is the fetch date, so publishing every
night regardless would tell every station an update was waiting, every night, forever.

The digest is over the taxonomy as the package stores it rather than over whatever bytes
upstream served, because the package writes its own formatting. build_packages.py records
the same digest as a control field, so the two are always comparing the same thing.

--no-project because this imports nothing but the standard library and one module that does
the same.
"""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT))

from backyardchirps.integrations.birdnet import TaxonomyDownloadError
from backyardchirps.integrations.birdnet import download_taxonomy
from tools.build_packages import TAXONOMY_IN_CHECKOUT
from tools.build_packages import taxonomy_bytes
from tools.build_packages import taxonomy_digest


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the taxonomy and print its digest.")
    parser.add_argument(
        "--out",
        type=Path,
        default=TAXONOMY_IN_CHECKOUT,
        help="where to write the downloaded taxonomy (default: this checkout's generated copy)",
    )
    arguments = parser.parse_args()

    try:
        taxa = download_taxonomy()
    except TaxonomyDownloadError as error:
        print(f"Could not read the taxonomy: {error}", file=sys.stderr)
        _fail(str(error))

    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_bytes(taxonomy_bytes(taxa))
    print(f"[taxonomy] {len(taxa)} species written to {arguments.out}", file=sys.stderr)
    print(taxonomy_digest(taxa))


def _fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
