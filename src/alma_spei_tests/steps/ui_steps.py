"""Reusable steps for the Polish UI (shell, auth panel, donor and import screens)."""

from playwright.sync_api import Locator, Page, Response, Route, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import ApiPath, ContentType
from alma_spei_tests.data import DonorProfile, Financial
from alma_spei_tests.pages import (
    AccountMessages,
    AccountsPage,
    AppPage,
    DonorCardPage,
    DonorListPage,
    DonorMessages,
    ExecutionMessages,
    ExecutionPage,
    ImportMessages,
    ImportsPage,
    LoginPage,
    ReviewMessages,
    ReviewPage,
)
from alma_spei_tests.steps import step


# --- form controls ------------------------------------------------------------
def tick(checkbox: Locator):
    """Click a checkbox and wait until it shows as checked.

    The app's checkboxes are controlled by Reagent/re-frame state that renders
    on the next animation frame, so ``Locator.check()`` (which verifies the
    state right after its click) reports a false failure.
    """
    checkbox.click()
    expect(checkbox).to_be_checked()


# --- shell --------------------------------------------------------------------
def _is_readiness_probe(response: Response) -> bool:
    return response.url.endswith(ApiPath.HEALTH_READY)


@step("Open the application shell and wait for its health check")
def open_application(page: Page) -> AppPage:
    with page.expect_response(_is_readiness_probe):
        app = AppPage(page).open()
    return app


@step("Make the readiness probe answer HTTP {status} with {body}")
def fake_readiness(page: Page, status: int, body: str):
    """Route the shell's health check to a canned answer (the backend is untouched)."""

    def answer(route: Route):
        route.fulfill(status=status, content_type=ContentType.JSON, body=body)

    page.route(f"**{ApiPath.HEALTH_READY}", answer)


@step("Let the readiness probe reach the backend again")
def restore_readiness(page: Page):
    page.unroute(f"**{ApiPath.HEALTH_READY}")


@step("Re-check the connection from the notice")
def trigger_recheck(app: AppPage) -> AppPage:
    with app.page.expect_response(_is_readiness_probe):
        app.recheck_button.click()
    return app


# --- dialogs ------------------------------------------------------------------
@step("Accept the next browser confirmation")
def confirm_next_dialog(page: Page):
    """Save and reset ask ``window.confirm`` first; accept the next one."""
    page.once("dialog", lambda dialog: dialog.accept())


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
    expect(login.signed_in_as(display_name)).to_be_visible()
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
    tick(imports.retry_confirmation)
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
    """Select the row once the editor is idle, then wait for that row's decision.

    While a decision loads, changing rows asks to discard a draft (a browser
    confirm the test would dismiss), so the editor must be idle first.
    """
    expect(review.idle_editor).to_be_visible()
    review.select_row(row)
    expect(review.source_card).to_contain_text(ReviewMessages.source_location(row))
    expect(review.idle_editor).to_be_visible()
    return review


@step("Search for '{text}' and compare with '{name}'")
def compare_with_donor(review: ReviewPage, text: str, name: str, city: str) -> ReviewPage:
    review.search_donor(text)
    review.compare_button(name, city).click()
    return review


# --- review decisions (task 38) -----------------------------------------------
@step("Choose the compared donor as the row's target")
def choose_compared_donor(review: ReviewPage, name: str) -> ReviewPage:
    expect(review.card_value(review.donor_card, ReviewMessages.DONOR_NAME)).to_have_text(name)
    review.editor_button(ReviewMessages.CHOOSE_COMPARED).click()
    expect(review.target_line).to_have_text(
        ReviewMessages.target(ReviewMessages.TARGET_EXISTING, name)
    )
    return review


@step("Fill in the payment review ({financial.currency}, {financial.disposition})")
def fill_payment_review(review: ReviewPage, financial: Financial) -> ReviewPage:
    review.currency_input.fill(financial.currency or "")
    review.evidence_input.fill(financial.evidence)
    review.disposition_select.select_option(financial.disposition.value)
    if financial.overlap_checked:
        tick(review.overlap_checkbox)
    return review


@step("Save the row decision through the form")
def save_decision_via_form(review: ReviewPage) -> ReviewPage:
    review.editor_button(ReviewMessages.SAVE_DECISION).click()
    expect(review.saved_notice).to_be_visible()
    expect(review.idle_editor).to_be_visible()
    return review


@step("Propose donor '{profile.name}' through the form and use it")
def propose_and_use_donor(review: ReviewPage, profile: DonorProfile) -> ReviewPage:
    review.editor_button(ReviewMessages.NEW_PROFILE).click()
    review.proposal_type_select.select_option(profile.entity_type.value)
    review.proposal_field("name").fill(profile.name)
    review.proposal_field("city").fill(profile.city)
    tick(review.proposal_check(ReviewMessages.CHECKED_EXISTING))
    tick(review.proposal_check(ReviewMessages.CHECKED_PROPOSALS))
    review.editor_button(ReviewMessages.SAVE_PROPOSAL).click()
    review.saved_proposal.get_by_role("button", name=ReviewMessages.USE_PROPOSAL).click()
    expect(review.target_line).to_have_text(
        ReviewMessages.target(ReviewMessages.TARGET_PROPOSAL, profile.name)
    )
    return review


@step("Prepare the import preview through the form")
def prepare_preview_via_form(review: ReviewPage) -> ReviewPage:
    expect(review.idle_editor).to_be_visible()
    review.preview_button(ReviewMessages.PREPARE_PREVIEW).click()
    return review


# --- confirmation, history and undo (task 40) ---------------------------------
@step("Open the import history from the navigation")
def open_history(page: Page) -> ExecutionPage:
    execution = ExecutionPage(page).open_history_from_nav()
    expect(execution.heading(ExecutionMessages.HISTORY_HEADING)).to_be_visible()
    return execution


@step("Open the confirmation of preview {preview_id} of import {batch_id}")
def open_confirmation(page: Page, batch_id: str, preview_id: str) -> ExecutionPage:
    execution = ExecutionPage(page).open_confirmation(batch_id, preview_id)
    expect(execution.heading(ExecutionMessages.CONFIRM_HEADING)).to_be_visible()
    expect(execution.text(ExecutionMessages.SYNTHETIC_MODE)).to_be_visible()
    return execution


@step("Request the test backup receipt, consent and commit")
def commit_via_confirmation(execution: ExecutionPage) -> ExecutionPage:
    execution.button(ExecutionMessages.REQUEST_BACKUP).click()
    expect(execution.backup_status).to_be_visible()
    tick(execution.consent_checkbox)
    execution.button(ExecutionMessages.COMMIT).click()
    expect(execution.heading(ExecutionMessages.OUTCOME_HEADING)).to_be_visible()
    return execution


@step("Open the outcome of import {batch_id}")
def open_outcome(page: Page, batch_id: str) -> ExecutionPage:
    execution = ExecutionPage(page).open_outcome(batch_id)
    expect(execution.heading(ExecutionMessages.OUTCOME_HEADING)).to_be_visible()
    return execution


@step("Open the undo dialog")
def open_undo_dialog(execution: ExecutionPage) -> ExecutionPage:
    undo = execution.button(ExecutionMessages.UNDO)
    expect(undo).to_be_enabled()
    undo.click()
    expect(execution.undo_dialog).to_be_visible()
    return execution


def imports_page(page: Page) -> ImportsPage:
    """The upload form shown inside another screen (e.g. the re-import context)."""
    return ImportsPage(page)


# --- account management (task 58) ---------------------------------------------
@step("Open the account management panel")
def open_accounts(page: Page) -> AccountsPage:
    accounts = AccountsPage(page).open_from_nav()
    expect(accounts.heading).to_be_visible()
    return accounts


@step("Create account {username} through the panel")
def create_account_via_panel(accounts: AccountsPage, username: str, display_name: str) -> str:
    """Create the account and return the one-time temporary password the panel shows."""
    accounts.create(username, display_name)
    expect(accounts.temporary_password).not_to_be_empty()
    return accounts.temporary_password.inner_text()


@step("Reset the password of {username} through the panel")
def reset_password_via_panel(accounts: AccountsPage, username: str) -> str:
    confirm_next_dialog(accounts.page)
    accounts.account_button(username, AccountMessages.RESET_PASSWORD).click()
    expect(accounts.temporary_password).not_to_be_empty()
    return accounts.temporary_password.inner_text()


@step("Deactivate {username} through the panel")
def deactivate_via_panel(accounts: AccountsPage, username: str) -> AccountsPage:
    accounts.active_checkbox(username).uncheck()
    confirm_next_dialog(accounts.page)
    with accounts.page.expect_response(lambda r: r.request.method == "PATCH"):
        accounts.account_button(username, AccountMessages.SAVE).click()
    return accounts
