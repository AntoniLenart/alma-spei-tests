"""Fixtures shared across the test layers.

Resource fixtures follow the create-in-setup / tear-down-after-yield pattern so
cleanup always runs, independent of whether the test passed:

* ``donor_factory`` / ``donor`` - donors created through the API; archived in
  the database afterwards (the API has no delete/archive endpoint), so they drop
  out of the default active list. Names carry the test's ``tag``.
* ``account_factory`` / ``staff`` - accounts created by the admin; deactivated
  afterwards (which also ends their sessions).
* ``staff_api`` - a staff account signed in on its own session, password
  rotated, for scenarios that must not touch the shared admin session.
* ``admin_id`` - the QA administrator's user id, a valid author for rows that
  database probes insert (and always roll back).

Logins are throttled per client address (30 per 15 minutes), so e2e tests that
are not about logging in borrow an API session via ``signed_in_page`` instead of
logging in through the form.
"""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from playwright.sync_api import Page

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import KNOWN_PASSWORD
from alma_spei_tests.data import (
    DonorFactory,
    DonorProfile,
    ProvisionedAccount,
    SyntheticAccount,
    new_account,
    new_donor_profile,
    unique_tag,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.pages import AppPage
from alma_spei_tests.steps import auth_steps, db_steps, donors_steps, ui_steps


# --- data ---------------------------------------------------------------------
@pytest.fixture
def tag() -> str:
    """A per-test marker embedded in donor names, for search isolation."""
    return unique_tag()


@pytest.fixture
def donor_factory(api: AlmaSpeiApi, db: DbQueries) -> Iterator[DonorFactory]:
    created: list[str] = []

    def create(profile: DonorProfile) -> dict[str, Any]:
        donor = donors_steps.create_donor(api, profile)
        created.append(donor["id"])
        return donor

    yield create
    for donor_id in created:
        db.archive_donor(donor_id)


@pytest.fixture
def donor_profile(tag: str) -> DonorProfile:
    return new_donor_profile(tag=tag)


@pytest.fixture
def donor(donor_factory: DonorFactory, donor_profile: DonorProfile) -> dict[str, Any]:
    """One active individual donor (as returned by the API), tagged for this test."""
    return donor_factory(donor_profile)


# --- accounts -----------------------------------------------------------------
@pytest.fixture
def account_factory(api: AlmaSpeiApi) -> Iterator[Callable[..., ProvisionedAccount]]:
    created: list[ProvisionedAccount] = []

    def create(account: SyntheticAccount | None = None) -> ProvisionedAccount:
        provisioned = auth_steps.create_account(api, account or new_account())
        created.append(provisioned)
        return provisioned

    yield create
    for provisioned in created:
        auth_steps.deactivate_account(api, provisioned.id, provisioned.display_name)


@pytest.fixture
def staff(account_factory: Callable[..., ProvisionedAccount]) -> ProvisionedAccount:
    """A new non-admin account that still has its temporary password."""
    return account_factory()


@pytest.fixture
def staff_api(
    staff: ProvisionedAccount, settings: Settings, base_url: str
) -> Iterator[AlmaSpeiApi]:
    """``staff`` signed in on its own session, temporary password rotated."""
    client = AlmaSpeiApi.connect(base_url, timeout=settings.http_timeout_s)
    try:
        client.sign_in(staff.username, staff.temporary_password, new_password=KNOWN_PASSWORD)
        yield client
    finally:
        client.close()


@pytest.fixture
def admin_id(db: DbQueries, settings: Settings) -> str:
    """The QA administrator's user id, read from the database."""
    return db_steps.read_user(db, settings.admin_username)["id"]


# --- browser ------------------------------------------------------------------
@pytest.fixture
def app_page(page: Page) -> AppPage:
    """A fresh AppPage per test (pytest-playwright provides ``page``)."""
    return AppPage(page)


@pytest.fixture
def signed_in_page(page: Page, api: AlmaSpeiApi, base_url: str) -> Page:
    """A browser page sharing the admin's API session (no UI login spent)."""
    ui_steps.share_session_with_browser(page, api, base_url)
    return page
