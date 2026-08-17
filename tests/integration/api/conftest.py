"""
API integration fixtures.

These stub out the slow and external calls the endpoints under test can reach, so that no
API test touches the network or the eBird rasters. species_detail imports them by name,
which is why they are patched in the features.species.views namespace.

Weather and astronomy need no stub: with no location configured, which is how the tests
run, they give up before computing or calling anything.
"""

import pytest

from backyardchirps.features.species import views as species_api


@pytest.fixture(autouse=True)
def stub_external_integrations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(species_api, "get_xeno_canto_recordings", lambda *args, **kwargs: [])
    monkeypatch.setattr(species_api, "get_yearly_seasonality", lambda *args, **kwargs: None)
