"""
API integration fixtures.

These stub out the slow calls the endpoints under test can reach, so that no API test
reads the eBird rasters. species_detail imports get_yearly_seasonality by name, which is
why it is patched in the features.species.views namespace.

Three things need no stub. Weather and astronomy give up before computing or calling
anything, since the tests run with no location configured. Reference calls come from the
installed region pack, and a test run has none, so they answer with an empty list without
leaving the machine.
"""

import pytest

from backyardchirps.features.species import views as species_api


@pytest.fixture(autouse=True)
def stub_external_integrations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(species_api, "get_yearly_seasonality", lambda *args, **kwargs: None)
