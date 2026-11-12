"""Contract tests: session and account responses vs contracts/auth.cljc."""

import allure
import pytest

from alma_spei_tests.assertions import assert_matches_contract
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.contracts import (
    ACCOUNT_RESPONSE,
    ACCOUNTS_RESPONSE,
    SESSION_RESPONSE,
    TEMPORARY_RESPONSE,
)
from alma_spei_tests.data import ProvisionedAccount
from alma_spei_tests.steps import auth_steps
from alma_spei_tests.testbase import BaseContractTest


@allure.feature("Auth contract")
class TestSessionContract(BaseContractTest):
    def test_anonymous_session_matches_contract(self, anonymous_api: AlmaSpeiApi):
        # 1. Inspect a signed-out session
        # 2. Verification: the body satisfies session-response (user null)
        body = auth_steps.inspect_session(anonymous_api).json()
        assert_matches_contract(body, SESSION_RESPONSE, "session-response")

    def test_signed_in_session_matches_contract(self, api: AlmaSpeiApi):
        # 1. Inspect the signed-in admin session
        # 2. Verification: the body satisfies session-response (with principal)
        body = auth_steps.inspect_session(api).json()
        assert_matches_contract(body, SESSION_RESPONSE, "session-response")


@allure.feature("Auth contract")
class TestAccountsContract(BaseContractTest):
    @pytest.mark.usefixtures("staff")
    def test_account_list_matches_contract(self, api: AlmaSpeiApi):
        # 1. Ensure at least one non-admin account exists, then list accounts
        # 2. Verification: the body satisfies accounts-response
        body = auth_steps.list_accounts(api).json()
        assert_matches_contract(body, ACCOUNTS_RESPONSE, "accounts-response")

    def test_account_edit_matches_contract(self, api: AlmaSpeiApi, staff: ProvisionedAccount):
        # 1. Edit a staff account without changing anything material
        # 2. Verification: the body satisfies account-response
        body = auth_steps.edit_account(
            api, staff.id, staff.display_name, active=True, administrator=False
        ).json()
        assert_matches_contract(body, ACCOUNT_RESPONSE, "account-response")

    def test_password_reset_matches_contract(self, api: AlmaSpeiApi, staff: ProvisionedAccount):
        # 1. Reset a staff account's password
        # 2. Verification: the body satisfies temporary-response
        body = auth_steps.reset_password(api, staff.id).json()
        assert_matches_contract(body, TEMPORARY_RESPONSE, "temporary-response")
