"""Reusable steps for the Polish UI (shell, auth panel, donor screens)."""

from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.pages import (
    AppPage,
    DonorListPage,
    LoginPage,
    ShellMessages,
)
from alma_spei_tests.steps import step


# --- shell --------------------------------------------------------------------
@step("Open the application shell")
def open_application(page: Page) -> AppPage:
    return AppPage(page).open()


@step("Wait for the shell to report readiness")
def wait_until_ready(app: AppPage) -> AppPage:
    app.wait_for_status(ShellMessages.OK)
    return app


@step("Trigger a connection re-check")
def trigger_recheck(app: AppPage) -> AppPage:
    app.click_recheck()
    return app


# --- auth panel ---------------------------------------------------------------
@step("Hand the API session's cookies to the browser")
def share_session_with_browser(page: Page, api: AlmaSpeiApi, base_url: str):
    """Sign the browser in as the API session's user without a UI login.

    Logins are throttled per client address, so e2e tests that are not about
    logging in reuse an existing session instead of spending login attempts.
    """
    page.context.add_cookies(
        [
            {"name": name, "value": value, "url": base_url}
            for name, value in api.session.cookies().items()
        ]
    )


@step("Open the login form")
def open_login(page: Page) -> LoginPage:
    login = LoginPage(page).open()
    expect(login.login_heading).to_be_visible()
    return login


@step("Log in through the form as {username}")
def log_in_via_form(login: LoginPage, username: str, password: str) -> LoginPage:
    login.log_in(username, password)
    return login


@step("Change the temporary password through the form")
def change_password_via_form(
    login: LoginPage, current: str, new: str, confirmation: str | None = None
) -> LoginPage:
    expect(login.password_form).to_be_visible()
    login.change_password(current, new, confirmation)
    return login


@step("Wait until signed in as {display_name}")
def wait_until_signed_in(login: LoginPage, display_name: str) -> LoginPage:
    expect(login.signed_in_banner(display_name)).to_be_visible()
    return login


@step("Log out through the nav")
def log_out_via_nav(login: LoginPage) -> LoginPage:
    login.logout_button.click()
    expect(login.login_heading).to_be_visible()
    return login


# --- donors -------------------------------------------------------------------
@step("Open the donor list")
def open_donor_list(page: Page) -> DonorListPage:
    login = LoginPage(page).open()
    login.donors_nav.click()
    donors = DonorListPage(page)
    expect(donors.heading).to_be_visible()
    return donors


@step("Search donors for '{text}'")
def search_donors(donors: DonorListPage, text: str) -> DonorListPage:
    donors.search(text)
    return donors


@step("Wait until the list shows {count} donor(s)")
def wait_for_row_count(donors: DonorListPage, count: int) -> DonorListPage:
    expect(donors.rows).to_have_count(count)
    return donors
