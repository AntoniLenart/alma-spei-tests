"""Reusable steps for the Polish UI (shell, auth panel, donor screens)."""

from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.pages import (
    AppPage,
    DonorCardPage,
    DonorListPage,
    DonorMessages,
    ImportMessages,
    ImportsPage,
    LoginPage,
    ReviewPage,
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


@step("Open the card of donor '{name}'")
def open_donor_card(donors: DonorListPage, name: str) -> DonorCardPage:
    donors.open_card(name)
    card = DonorCardPage(donors.page)
    expect(card.heading).to_have_text(name)
    return card


@step("Edit the donor's {field} to '{value}' and save")
def edit_and_save(card: DonorCardPage, field: str, value: str) -> DonorCardPage:
    card.start_editing()
    card.set_field(field, value)
    card.save()
    return card


@step("Wait for the save confirmation")
def wait_until_saved(card: DonorCardPage) -> DonorCardPage:
    expect(card.saved_notice).to_have_text(DonorMessages.SAVED)
    return card


# --- bank upload (task 36) ----------------------------------------------------
@step("Open the bank upload screen")
def open_imports(page: Page) -> ImportsPage:
    imports = ImportsPage(page).open_from_nav()
    expect(imports.heading).to_be_visible()
    return imports


@step("Choose '{filename}' in the upload form")
def choose_import_file(
    imports: ImportsPage, filename: str, content: bytes, separator: str | None = None
) -> ImportsPage:
    imports.choose_file(filename, content)
    if separator is not None:
        imports.choose_separator(separator)
    return imports


@step("Submit the file for analysis")
def submit_upload(imports: ImportsPage) -> ImportsPage:
    imports.upload_button.click()
    return imports


@step("Wait for the analysis status '{state_label}'")
def wait_for_import_state(imports: ImportsPage, state_label: str) -> ImportsPage:
    expect(imports.summary_value(ImportMessages.STATUS)).to_have_text(state_label)
    return imports


@step("Confirm and retry the analysis of '{filename}'")
def retry_upload(imports: ImportsPage, filename: str, content: bytes) -> ImportsPage:
    imports.choose_file(filename, content)
    imports.retry_confirmation.check()
    imports.retry_button.click()
    return imports


# --- import review (task 37) --------------------------------------------------
@step("Open the import review queue")
def open_review_queue(page: Page) -> ReviewPage:
    review = ReviewPage(page).open_from_nav()
    expect(review.heading).to_be_visible()
    return review


@step("Deep-link to the review of import {batch_id}")
def open_review_batch(page: Page, batch_id: str, filename: str) -> ReviewPage:
    review = ReviewPage(page).open_batch(batch_id)
    expect(review.batch_heading).to_have_text(filename)
    return review


@step("Pick staged row {row} for comparison")
def pick_review_row(review: ReviewPage, row: int) -> ReviewPage:
    review.select_row(row)
    return review


@step("Search for '{text}' and compare with '{name}'")
def compare_with_donor(review: ReviewPage, text: str, name: str, city: str) -> ReviewPage:
    review.search_donor(text)
    review.compare_button(name, city).click()
    return review
