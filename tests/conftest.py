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
* ``staged_upload`` / ``decided_upload`` / ``committed_import`` - a staged bank
  batch, the same batch with both rows decided, and then committed (no
  teardown: imports have no delete endpoint, review decisions write nothing
  canonical, and a commit is permanent, undoable-once history).

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
    BankStatement,
    DonorFactory,
    DonorProfile,
    ProvisionedAccount,
    SyntheticAccount,
    existing_donor,
    new_account,
    new_bank_statement,
    new_donor_profile,
    unique_tag,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.pages import AppPage
from alma_spei_tests.steps import (
    auth_steps,
    db_steps,
    donors_steps,
    execution_steps,
    imports_steps,
    review_steps,
    ui_steps,
)
from alma_spei_tests.steps.execution_steps import CommittedImport


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


# --- imports (task 35) ----------------------------------------------------------
@pytest.fixture
def bank_statement(tag: str) -> BankStatement:
    """Two valid synthetic statement lines, unique to this test (by tag)."""
    return new_bank_statement(tag)


@pytest.fixture
def staged_upload(api: AlmaSpeiApi, bank_statement: BankStatement, tag: str) -> dict[str, Any]:
    """The upload report of ``bank_statement`` staged as a CSV import.

    No teardown: staged imports have no cancel/delete endpoint yet and the app
    role cannot delete them. Unique file bytes per test keep runs independent
    (the backend refuses a byte-identical file twice).
    """
    return imports_steps.upload_staged(api, f"{tag}.csv", bank_statement.to_csv())


# --- review decisions (task 38) -------------------------------------------------
@pytest.fixture
def staged_batch_id(staged_upload: dict[str, Any]) -> str:
    return staged_upload["batch"]["id"]


@pytest.fixture
def decided_upload(api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]) -> dict[str, Any]:
    """``staged_upload`` with both rows linked to ``donor`` as new PLN payments.

    Returns the last decision response (its ``batch`` is current). Decisions
    write nothing canonical, so there is nothing to clean up.
    """
    decision = existing_donor(donor)
    return review_steps.decide_rows(api, staged_batch_id, [decision, decision])


# --- commit and undo (task 39) ----------------------------------------------------
@pytest.fixture
def committed_import(api: AlmaSpeiApi, decided_upload: dict[str, Any]) -> CommittedImport:
    """``decided_upload`` previewed, backed up (synthetic receipt) and committed.

    No teardown: a commit is permanent history, and undo is itself under test
    (only the latest commit can be undone). ``donor`` is archived afterwards as
    usual; its imported payments stay attributed to this batch.
    """
    return execution_steps.commit_import(api, decided_upload["batch"]["id"])


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
