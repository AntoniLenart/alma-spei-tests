"""E2E tests for signing in through the Polish auth panel.

These are the only e2e tests that spend real login attempts (logins are
throttled per client address); everything else borrows an API session.
"""

import allure
from assertpy import assert_that, soft_assertions
from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import KNOWN_PASSWORD, WRONG_PASSWORD, ApiErrorPayload
from alma_spei_tests.data import ProvisionedAccount
from alma_spei_tests.pages import AuthMessages, LoginPage
from alma_spei_tests.steps import ui_steps
from alma_spei_tests.testbase import BaseE2ETest


@allure.feature("Login UI")
class TestLoginForm(BaseE2ETest):
    def test_signed_out_visitor_sees_the_login_form(self, page: Page):
        # 1. Open the app without a session
        # 2. Verification: the "Logowanie" form with username, password and submit is shown
        login = ui_steps.open_login(page)
        with soft_assertions():
            for name, locator in {
                "username field": login.username_input,
                "password field": login.password_input,
                "submit button": login.login_button,
            }.items():
                assert_that(locator.is_visible()).described_as(
                    f"the login {name} should be visible"
                ).is_true()

    def test_wrong_password_shows_the_polish_error(self, page: Page, staff: ProvisionedAccount):
        # 1. Open the login form
        # 2. Log in with a wrong password
        # 3. Verification: the backend's Polish invalid-credentials message is shown as an alert
        login = ui_steps.open_login(page)
        ui_steps.log_in_via_form(login, staff.username, WRONG_PASSWORD)
        expect(login.alert).to_have_text(ApiErrorPayload.INVALID_CREDENTIALS["message"])


@allure.feature("Login UI")
class TestFirstLogin(BaseE2ETest):
    def test_first_login_forces_a_password_change_then_signs_in(
        self, page: Page, staff: ProvisionedAccount
    ):
        # 1. Log in through the form with the temporary password
        # 2. Verify the forced "Zmiana hasła" screen with its notice
        # 3. Change the password through the form
        # 4. Verification: signed in as the account, with the donor navigation available
        login = ui_steps.open_login(page)
        ui_steps.log_in_via_form(login, staff.username, staff.temporary_password)
        expect(login.temporary_notice).to_be_visible()
        ui_steps.change_password_via_form(login, staff.temporary_password, KNOWN_PASSWORD)
        ui_steps.wait_until_signed_in(login, staff.display_name)
        expect(login.donors_nav).to_be_visible()

    def test_mismatched_confirmation_is_caught_in_the_form(
        self, page: Page, staff: ProvisionedAccount
    ):
        # 1. Log in through the form with the temporary password
        # 2. Submit the password change with a different confirmation
        # 3. Verification: the Polish mismatch message is shown and the form stays open
        login = ui_steps.open_login(page)
        ui_steps.log_in_via_form(login, staff.username, staff.temporary_password)
        ui_steps.change_password_via_form(
            login, staff.temporary_password, KNOWN_PASSWORD, confirmation=WRONG_PASSWORD
        )
        expect(login.alert).to_have_text(AuthMessages.PASSWORDS_DIFFER)
        assert_that(login.password_form.is_visible()).described_as(
            "the password form should stay open"
        ).is_true()


@allure.feature("Login UI")
class TestSignedInChrome(BaseE2ETest):
    def test_admin_sees_account_management(self, signed_in_page: Page, settings: Settings):
        # 1. Open the app with the administrator's session
        # 2. Verification: signed-in banner, Start screen and the accounts navigation
        login = LoginPage(signed_in_page).open()
        ui_steps.wait_until_signed_in(login, settings.admin_display_name)
        with soft_assertions():
            assert_that(login.home_heading.is_visible()).described_as(
                "the Start screen should be shown"
            ).is_true()
            assert_that(login.accounts_nav.is_visible()).described_as(
                "an administrator should see account management"
            ).is_true()

    def test_logout_returns_to_the_login_form_and_ends_the_session(
        self, page: Page, base_url: str, staff: ProvisionedAccount, staff_api: AlmaSpeiApi
    ):
        # 1. Open the app with a signed-in staff session
        # 2. Log out through the navigation
        # 3. Verification: the login form is back and the API session no longer resolves
        ui_steps.share_session_with_browser(page, staff_api, base_url)
        login = LoginPage(page).open()
        ui_steps.wait_until_signed_in(login, staff.display_name)
        ui_steps.log_out_via_nav(login)
        assert_that(staff_api.current_user()).described_as(
            "logging out in the browser should end the shared session"
        ).is_none()
