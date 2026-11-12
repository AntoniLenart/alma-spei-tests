"""Fixtures shared across the test layers.

Resource fixtures follow the create-in-setup / tear-down-after-yield pattern so
cleanup always runs, independent of whether the test passed:

* ``account_factory`` / ``staff`` - accounts created by the admin; deactivated
  afterwards (which also ends their sessions).
* ``staff_api`` - a staff account signed in on its own session, password
  rotated, for scenarios that must not touch the shared admin session.

Logins are throttled per client address (30 per 15 minutes), so e2e tests that
are not about logging in borrow an API session via ``signed_in_page`` instead of
logging in through the form.
"""

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Page

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import KNOWN_PASSWORD
from alma_spei_tests.data import (
    ProvisionedAccount,
    SyntheticAccount,
    new_account,
)
from alma_spei_tests.pages import AppPage
from alma_spei_tests.steps import auth_steps, ui_steps


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
