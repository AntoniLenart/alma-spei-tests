"""E2E tests for the final import confirmation, history and undo screens (task 40).

The browser borrows the administrator's API session. Batches are staged and
decided through the API; the import summary leads to the confirmation, and the
screen under test performs the explicit actions:
the labelled test backup receipt, the consent, the commit, and the confirmed
undo. Opening a screen must never write anything.
"""

from typing import Any

import allure
import pytest
from assertpy import assert_that
from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import REVIEW_CURRENCY, CsvSeparator, ImportState
from alma_spei_tests.data import (
    BankStatement,
    DonorFactory,
    existing_donor,
    new_bank_statement,
    new_donor_profile,
    proposed_donor,
)
from alma_spei_tests.pages import ExecutionMessages, ReviewPage
from alma_spei_tests.steps import execution_steps, imports_steps, review_steps, ui_steps
from alma_spei_tests.steps.execution_steps import CommittedImport
from alma_spei_tests.testbase import BaseE2ETest

#: The donor reference and both payments of a decided two-line batch.
PLANNED_CHANGES = 3

#: Undoing an import and loading the file again makes its second attempt.
REIMPORT_ATTEMPT = 2


@allure.feature("Import confirmation UI")
class TestConfirmationUi(BaseE2ETest):
    def test_the_summary_leads_to_the_confirmation(
        self, signed_in_page: Page, decided_upload: dict[str, Any]
    ):
        # 1. Decide both rows through the API (fixture)
        # 2. Open the batch's summary and choose "Sprawdź zmiany i zatwierdź"
        # 3. Verification: the confirmation shows the scope and every planned change, the
        #    unchanged-profiles note and the synthetic-mode warning; committing is disabled
        #    before a receipt and consent
        batch = decided_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        execution = ui_steps.review_changes(review)
        expect(execution.text(ExecutionMessages.summary(0, 2, 0))).to_be_visible()
        expect(execution.preview_items).to_have_count(PLANNED_CHANGES)
        expect(execution.text(ExecutionMessages.NO_FIELD_CHANGES)).to_be_visible()
        expect(execution.text(ExecutionMessages.SYNTHETIC_MODE)).to_be_visible()
        expect(execution.button(ExecutionMessages.COMMIT)).to_be_disabled()

    def test_an_explicit_receipt_and_consent_commit_the_import(
        self,
        signed_in_page: Page,
        api: AlmaSpeiApi,
        decided_upload: dict[str, Any],
        settings: Settings,
    ):
        # 1. Prepare a preview through the API and open its confirmation
        # 2. Request the test backup receipt, give consent and commit
        # 3. Verification: the outcome screen shows the saved commit by the admin with the
        #    PLN total; the API reports the batch committed
        batch_id = decided_upload["batch"]["id"]
        preview = review_steps.create_preview(api, batch_id)["preview"]
        execution = ui_steps.open_confirmation(signed_in_page, batch_id, preview["id"])
        ui_steps.commit_via_confirmation(execution)
        total = preview["summary"]["totals"][0]["amount"]
        expect(execution.heading(ExecutionMessages.COMMITTED_SECTION)).to_be_visible()
        expect(execution.screen).to_contain_text(
            ExecutionMessages.committed_by(settings.admin_display_name)
        )
        expect(execution.text(ExecutionMessages.total(total, REVIEW_CURRENCY))).to_be_visible()
        state = execution_steps.read_outcome(api, batch_id).json()["batch"]["state"]
        assert_that(state).described_as("the screen should commit the import").is_equal_to(
            ImportState.COMMITTED
        )

    def test_opening_the_confirmation_writes_nothing(
        self, signed_in_page: Page, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Prepare a preview through the API and open its confirmation, without any action
        # 2. Verification: the batch is still under review, uncommitted
        batch_id = decided_upload["batch"]["id"]
        preview = review_steps.create_preview(api, batch_id)["preview"]
        ui_steps.open_confirmation(signed_in_page, batch_id, preview["id"])
        outcome = execution_steps.read_outcome(api, batch_id).json()
        assert_that((outcome["batch"]["state"], outcome["commit"])).described_as(
            "opening the confirmation should not commit"
        ).is_equal_to((ImportState.REVIEW, None))


@allure.feature("Import history UI")
class TestHistoryUi(BaseE2ETest):
    def test_history_lists_the_committed_import_and_opens_its_outcome(
        self,
        signed_in_page: Page,
        committed_import: CommittedImport,
        settings: Settings,
    ):
        # 1. Commit a batch through the API (fixture)
        # 2. Open the history from the navigation, then the entry's details
        # 3. Open the batch's outcome
        # 4. Verification: the entry shows the committed state and, in its details, the
        #    uploader; the outcome shows the saved commit
        filename = committed_import.outcome["batch"]["original-filename"]
        execution = ui_steps.open_history(signed_in_page)
        entry = execution.history_entry(filename)
        expect(execution.state_badge(entry)).to_have_text(ExecutionMessages.STATE_COMMITTED)
        execution.open_entry_details(entry)
        expect(execution.context_value(ExecutionMessages.UPLOADED_BY, entry)).to_have_text(
            settings.admin_display_name
        )
        expect(execution.context_value(ExecutionMessages.STATE, entry)).to_have_text(
            ExecutionMessages.STATE_COMMITTED
        )
        entry.get_by_role("link", name=ExecutionMessages.OPEN_OUTCOME).click()
        expect(execution.heading(ExecutionMessages.COMMITTED_SECTION)).to_be_visible()


@allure.feature("Import undo UI")
class TestUndoUi(BaseE2ETest):
    def test_cancelling_the_undo_dialog_changes_nothing(
        self, signed_in_page: Page, api: AlmaSpeiApi, committed_import: CommittedImport
    ):
        # 1. Commit a batch through the API (fixture) and open its outcome
        # 2. Open the undo dialog and cancel it
        # 3. Verification: the dialog closes; the batch stays committed
        execution = ui_steps.open_outcome(signed_in_page, committed_import.batch_id)
        ui_steps.open_undo_dialog(execution)
        execution.dialog_button(ExecutionMessages.CANCEL_UNDO).click()
        expect(execution.undo_dialog).to_be_hidden()
        state = execution_steps.read_outcome(api, committed_import.batch_id).json()["batch"][
            "state"
        ]
        assert_that(state).described_as("cancelling should undo nothing").is_equal_to(
            ImportState.COMMITTED
        )

    def test_a_confirmed_undo_removes_the_imported_donor_from_the_list(
        self, signed_in_page: Page, api: AlmaSpeiApi, staged_upload: dict[str, Any], tag: str
    ):
        # 1. Commit through the API a batch whose rows created one proposed donor
        # 2. Open its outcome, open the undo dialog and confirm
        # 3. Verification: the undone outcome counts two reversed payments and one archived
        #    profile; the donor list no longer finds the imported donor
        batch_id = staged_upload["batch"]["id"]
        proposal = review_steps.create_proposal(
            api, batch_id, new_donor_profile(tag=tag).to_payload()
        )
        review_steps.decide_rows(
            api, batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        execution_steps.commit_import(api, batch_id)
        execution = ui_steps.open_outcome(signed_in_page, batch_id)
        ui_steps.open_undo_dialog(execution)
        execution.dialog_button(ExecutionMessages.CONFIRM_UNDO).click()
        expect(execution.heading(ExecutionMessages.UNDONE_HEADING)).to_be_visible()
        expect(execution.screen).to_contain_text(ExecutionMessages.undo_counts(2, 1))
        donors = ui_steps.open_donor_list(signed_in_page)
        ui_steps.search_donors(donors, tag)
        expect(donors.empty_message).to_be_visible()

    @pytest.mark.usefixtures("later_commit")
    def test_an_older_import_offers_no_undo(
        self, signed_in_page: Page, committed_import: CommittedImport
    ):
        # 1. Commit a batch, then commit a second one (fixtures)
        # 2. Open the first batch's outcome
        # 3. Verification: the not-latest reason is shown and the undo button is disabled
        execution = ui_steps.open_outcome(signed_in_page, committed_import.batch_id)
        expect(execution.text(ExecutionMessages.NOT_LATEST)).to_be_visible()
        expect(execution.button(ExecutionMessages.UNDO)).to_be_disabled()


@allure.feature("Import undo UI")
class TestReimportUi(BaseE2ETest):
    def test_the_undone_file_can_be_reimported_as_a_fresh_attempt(
        self,
        signed_in_page: Page,
        api: AlmaSpeiApi,
        committed_import: CommittedImport,
        bank_statement: BankStatement,
        tag: str,
    ):
        # 1. Commit a batch (fixture) and undo it through the API
        # 2. Open its outcome and follow "Wczytaj ten sam plik ponownie"
        # 3. Choose the same file and separator, confirm PLN and the retry, and retry
        # 4. Verification: the summary of the file opens for a new batch: attempt 2, staged and
        #    awaiting review
        filename = f"{tag}.csv"
        execution_steps.undo_import(api, committed_import)
        execution = ui_steps.open_outcome(signed_in_page, committed_import.batch_id)
        execution.link(ExecutionMessages.REIMPORT).click()
        expect(execution.heading(ExecutionMessages.REIMPORT_HEADING)).to_be_visible()
        imports = ui_steps.imports_page(signed_in_page)
        ui_steps.choose_import_file(
            imports, filename, bank_statement.to_csv(), CsvSeparator.SEMICOLON
        )
        ui_steps.retry_upload(imports, filename, bank_statement.to_csv())
        review = ui_steps.wait_for_summary(ReviewPage(signed_in_page), filename)
        assert_that(review.batch_id).described_as(
            "the re-import should be staged as a new batch"
        ).is_not_none().is_not_equal_to(committed_import.batch_id)
        batch = execution_steps.read_outcome(api, str(review.batch_id)).json()["batch"]
        assert_that((batch["attempt-number"], batch["state"])).described_as(
            "the re-import should be a fresh attempt awaiting review"
        ).is_equal_to((REIMPORT_ATTEMPT, ImportState.REVIEW))


# --- file-local fixtures --------------------------------------------------------
@pytest.fixture
def later_commit(
    api: AlmaSpeiApi,
    committed_import: CommittedImport,
    donor_factory: DonorFactory,
    tag: str,
) -> CommittedImport:
    """A second batch, for another donor, committed after ``committed_import``."""
    other = donor_factory(new_donor_profile(tag=tag))
    later_tag = f"{tag}-later"
    statement = new_bank_statement(later_tag)
    batch = imports_steps.upload_staged(api, f"{later_tag}.csv", statement.to_csv())["batch"]
    review_steps.decide_rows(api, batch["id"], [existing_donor(other), existing_donor(other)])
    return execution_steps.commit_import(api, batch["id"])
