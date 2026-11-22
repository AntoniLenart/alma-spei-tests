"""E2E tests for the sign-in screen and the account management panel (task 58).

A signed-out visitor only gets the Polish sign-in form - there is no way to sign
up. A temporary password must be replaced by a policy-compliant one before any
work. Administrators create accounts, reset passwords and deactivate accounts in
the panel; a reset or deactivation ends the account's sessions at once. These
tests log in through the form or the API a few times, so each starts with fresh
login throttle buckets.
"""

import re
from collections.abc import Iterator

import allure
import pytest
from assertpy import assert_that, soft_assertions
from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    KNOWN_PASSWORD,
    ROTATED_PASSWORD,
    TEMPORARY_PASSWORD_MIN_LENGTH,
    WEAK_PASSWORD,
)
from alma_spei_tests.data import ProvisionedAccount, new_account
from alma_spei_tests.db import DbQueries
from alma_spei_tests.pages import AuthMessages, LoginPage
from alma_spei_tests.steps import auth_steps, ui_steps
from alma_spei_tests.testbase import BaseE2ETest

#: Anything that would offer a self-service account.
SIGN_UP_WORDING = re.compile(r"rejestr|załóż konto|utwórz konto", re.IGNORECASE)


@pytest.fixture(autouse=True)
def fresh_login_budget(db: DbQueries) -> Iterator[None]:
    """Each test here logs in; start it with empty login throttle buckets."""
    db.clear_auth_throttle()
    yield


@allure.feature("Accounts UI")
class TestSignInScreen(BaseE2ETest):
    def test_a_signed_out_visitor_gets_only_the_polish_sign_in(self, page: Page):
        # 1. Open the app without a session
        # 2. Verification: the "Logowanie" form, no navigation, nothing offering to sign up
        login = ui_steps.open_login(page)
        with soft_assertions():
            assert_that(login.main_nav.count()).described_as(
                "a signed-out visitor should get no navigation"
            ).is_equal_to(0)
            assert_that(page.get_by_text(SIGN_UP_WORDING).count()).described_as(
                "nothing should offer self-registration"
            ).is_equal_to(0)

    def test_a_weak_new_password_is_refused_before_any_access(
        self, page: Page, staff: ProvisionedAccount
    ):
        # 1. Log in through the form with a temporary password
        # 2. Try to change it to a password that breaks the policy
        # 3. Verification: the Polish policy message, the change form stays, and neither the
        #    donor register nor the imports are reachable yet
        login = ui_steps.open_login(page)
        ui_steps.log_in_via_form(login, staff.username, staff.temporary_password)
        ui_steps.change_password_via_form(login, staff.temporary_password, WEAK_PASSWORD)
        expect(login.alert).to_have_text(AuthMessages.PASSWORD_POLICY_FAILED)
        expect(login.password_form).to_be_visible()
        expect(login.donors_nav).to_have_count(0)
        expect(login.nav_button(AuthMessages.NEW_IMPORT_NAV)).to_have_count(0)

    def test_staff_change_their_own_password_from_the_navigation(
        self,
        page: Page,
        base_url: str,
        staff: ProvisionedAccount,
        staff_api: AlmaSpeiApi,
        anonymous_api: AlmaSpeiApi,
    ):
        # 1. Open the app with a signed-in staff session
        # 2. Choose "Zmień hasło" and change the password
        # 3. Verification: back on the Start screen, and the new password signs in
        ui_steps.share_session_with_browser(page, staff_api, base_url)
        login = LoginPage(page).open()
        login.nav_button(AuthMessages.CHANGE_PASSWORD_NAV).click()
        ui_steps.change_password_via_form(login, KNOWN_PASSWORD, ROTATED_PASSWORD)
        expect(login.home_heading).to_be_visible()
        response = auth_steps.login(anonymous_api, staff.username, ROTATED_PASSWORD)
        assert_that(response.json().get("user", {}).get("username")).described_as(
            "the new password should sign the account in"
        ).is_equal_to(staff.username)


@allure.feature("Accounts UI")
class TestAccountsPanel(BaseE2ETest):
    def test_an_administrator_creates_an_account_with_a_one_time_password(
        self,
        signed_in_page: Page,
        anonymous_api: AlmaSpeiApi,
        panel_accounts: list[str],
    ):
        # 1. Open the account panel as the administrator
        # 2. Create an account
        # 3. Close the temporary password box
        # 4. Verification: the account is listed; its temporary password was shown once and
        #    signs it in with a required password change
        account = new_account()
        accounts = ui_steps.open_accounts(signed_in_page)
        temporary = ui_steps.create_account_via_panel(
            accounts, account.username, account.display_name
        )
        panel_accounts.append(account.username)
        accounts.close_password_button.click()
        expect(accounts.temporary_password_box).to_be_hidden()
        expect(accounts.account_form(account.username)).to_be_visible()
        user = auth_steps.login(anonymous_api, account.username, temporary).json().get("user")
        with soft_assertions():
            assert_that(len(temporary)).described_as(
                "the temporary password should be a long random secret"
            ).is_greater_than_or_equal_to(TEMPORARY_PASSWORD_MIN_LENGTH)
            assert_that(user and user["password-change-required"]).described_as(
                "the temporary password should sign in with a required change"
            ).is_true()

    def test_a_password_reset_issues_a_new_one_time_password_and_ends_sessions(
        self, signed_in_page: Page, staff: ProvisionedAccount, staff_api: AlmaSpeiApi
    ):
        # 1. Sign a staff account in (its own session)
        # 2. Reset its password in the panel and confirm
        # 3. Verification: a new temporary password is shown, and the staff session ended
        accounts = ui_steps.open_accounts(signed_in_page)
        temporary = ui_steps.reset_password_via_panel(accounts, staff.username)
        with soft_assertions():
            assert_that(temporary).described_as(
                "the reset should issue a new temporary password"
            ).is_not_equal_to(staff.temporary_password)
            assert_that(staff_api.current_user()).described_as(
                "the reset should end the account's sessions"
            ).is_none()

    def test_deactivation_ends_the_sessions_at_once(
        self, signed_in_page: Page, staff: ProvisionedAccount, staff_api: AlmaSpeiApi
    ):
        # 1. Sign a staff account in (its own session)
        # 2. Untick "Konto aktywne" in the panel, save and confirm
        # 3. Verification: the staff session ended immediately
        accounts = ui_steps.open_accounts(signed_in_page)
        ui_steps.deactivate_via_panel(accounts, staff.username)
        assert_that(staff_api.current_user()).described_as(
            "deactivation should end the account's sessions at once"
        ).is_none()

    def test_staff_do_not_see_account_management(
        self, page: Page, base_url: str, staff_api: AlmaSpeiApi
    ):
        # 1. Open the app with a signed-in staff (non-administrator) session
        # 2. Verification: no "Konta użytkowników" in the navigation
        ui_steps.share_session_with_browser(page, staff_api, base_url)
        login = LoginPage(page).open()
        expect(login.donors_nav).to_be_visible()
        expect(login.accounts_nav).to_have_count(0)


# --- file-local fixtures ------------------------------------------------------
@pytest.fixture
def panel_accounts(api: AlmaSpeiApi) -> Iterator[list[str]]:
    """Usernames created through the panel; deactivated afterwards."""
    created: list[str] = []
    yield created
    if not created:
        return
    users = {u["username"]: u for u in auth_steps.list_accounts(api).json()["users"]}
    for username in created:
        if username in users:
            auth_steps.deactivate_account(
                api, users[username]["id"], users[username]["display-name"]
            )
