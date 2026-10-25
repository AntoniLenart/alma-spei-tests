"""Fixtures shared across the test layers.

Function-scoped page object for E2E tests and example resource fixtures live
here. Resource fixtures follow the create-in-setup / tear-down-after-yield
pattern so cleanup always runs, independent of whether the test passed.
"""

from collections.abc import Iterator

import pytest
from playwright.sync_api import Page

from alma_spei_tests.data import SyntheticDonor, new_donor
from alma_spei_tests.pages import AppPage


@pytest.fixture
def app_page(page: Page) -> AppPage:
    """A fresh AppPage per test (pytest-playwright provides ``page``)."""
    return AppPage(page)


@pytest.fixture
def synthetic_donor() -> Iterator[SyntheticDonor]:
    """Example resource fixture: a single synthetic donor.

    Today this is pure in-memory data (no donor API exists yet), so teardown is
    a no-op. When the donor API lands, create via the API here and delete after
    ``yield`` - the test body never has to remember to clean up.
    """
    donor = new_donor(seed=1)
    # setup: (future) persist via api.create_donor(donor) and capture its id
    yield donor
    # teardown: (future) api.archive_donor(donor_id) - always runs
