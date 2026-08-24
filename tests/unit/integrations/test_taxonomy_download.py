"""
The guard on the downloaded taxonomy, which is the only thing standing between an upstream
accident and every station writing it over the copy it has.

No network: the responses are built here and urlopen is replaced.
"""

import io
import json
from typing import Any

import pytest

from backyardchirps.integrations import birdnet
from backyardchirps.integrations.birdnet import TaxonomyDownloadError
from backyardchirps.integrations.birdnet import check_taxonomy
from backyardchirps.integrations.birdnet import download_taxonomy


def make_taxonomy(species_count: int) -> list[dict]:
    return [
        {
            "scientific_name": f"Genus species{index}",
            "common_names": {"en": f"Bird {index}"},
            "ebird_code": f"bird{index}",
            "taxon_group": "Aves",
        }
        for index in range(species_count)
    ]


class FakeResponse(io.BytesIO):
    """
    Enough of what urlopen returns for download_taxonomy: a context manager that reads.
    """

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *arguments: Any) -> None:
        self.close()


def test_a_full_taxonomy_passes() -> None:
    check_taxonomy(make_taxonomy(12_000))


def test_a_truncated_download_is_refused() -> None:
    with pytest.raises(TaxonomyDownloadError, match="expected at least"):
        check_taxonomy(make_taxonomy(200))


def test_an_entry_missing_a_required_key_is_refused() -> None:
    taxa = make_taxonomy(12_000)
    del taxa[500]["ebird_code"]

    with pytest.raises(TaxonomyDownloadError, match="Entry 500 has no ebird_code"):
        check_taxonomy(taxa)


def test_an_entry_with_an_empty_scientific_name_is_refused() -> None:
    taxa = make_taxonomy(12_000)
    taxa[7]["scientific_name"] = ""

    with pytest.raises(TaxonomyDownloadError, match="Entry 7 has an empty scientific_name"):
        check_taxonomy(taxa)


def test_an_answer_that_is_not_a_list_is_refused() -> None:
    with pytest.raises(TaxonomyDownloadError, match="got dict"):
        check_taxonomy({"error": "rate limited"})


def test_download_checks_what_it_got(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    An HTML error page served with a 200 is the case that matters: json.loads may well
    fail, but when it does not, nothing downstream would look at the shape.
    """
    monkeypatch.setattr(
        birdnet.urllib.request,
        "urlopen",
        lambda *arguments, **keyword_arguments: FakeResponse(json.dumps(make_taxonomy(3)).encode()),
    )

    with pytest.raises(TaxonomyDownloadError):
        download_taxonomy()


def test_download_returns_the_species_when_the_answer_is_whole(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        birdnet.urllib.request,
        "urlopen",
        lambda *arguments, **keyword_arguments: FakeResponse(json.dumps(make_taxonomy(12_000)).encode()),
    )

    assert len(download_taxonomy()) == 12_000
