"""Tests of the first-administrator bootstrap (task 57).

``bb create-admin`` runs the app's bootstrap: it creates the first account
administrator, interactively, and only on a database without accounts. The
orchestrated stack used exactly that service call to provision the QA
administrator, so it works on an empty database; here it must refuse to run
again, and the console command must refuse to run without a terminal. Neither
may create an account. Runs only against the orchestrated, disposable stack.
"""

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.config import Settings
from alma_spei_tests.constants import BootstrapMessage
from alma_spei_tests.data import new_account
from alma_spei_tests.db import DbQueries
from alma_spei_tests.orchestration import Stack
from alma_spei_tests.testbase import BaseDbTest

#: The non-zero exit both refusals end with.
FAILED_EXIT = 1


@pytest.fixture(autouse=True)
def orchestrated_only(settings: Settings):
    if not settings.orchestrate:
        pytest.skip("runs app commands; only against the orchestrated stack")


@allure.feature("Authentication schema")
class TestAdminBootstrap(BaseDbTest):
    def test_the_bootstrap_refuses_once_an_account_exists(self, stack: Stack, db: DbQueries):
        # 1. Run the first-administrator bootstrap for a new username
        # 2. Verification: it fails with "the first account already exists" and creates nobody
        account = new_account(administrator=True)
        result = stack.bootstrap_admin(account.username, account.display_name)
        with soft_assertions():
            assert_that(result.returncode).described_as(
                "a second bootstrap should fail"
            ).is_equal_to(FAILED_EXIT)
            assert_that(result.stderr).described_as(
                "the refusal should say the first account exists"
            ).contains(BootstrapMessage.ALREADY_DONE)
            assert_that(db.user(account.username)).described_as(
                "a refused bootstrap should create no account"
            ).is_none()

    def test_create_admin_needs_an_interactive_terminal(self, stack: Stack):
        # 1. Run the command behind `bb create-admin` with no console attached
        # 2. Verification: it fails with its generic Polish refusal
        result = stack.create_admin_without_terminal()
        with soft_assertions():
            assert_that(result.returncode).described_as(
                "create-admin should refuse to run without a terminal"
            ).is_equal_to(FAILED_EXIT)
            assert_that(result.stderr).described_as(
                "the refusal should be the Polish bootstrap message"
            ).contains(BootstrapMessage.FAILED)
