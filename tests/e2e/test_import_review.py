"""E2E tests for the Polish import review screen (task 37, automatic reconciliation).

The browser borrows the administrator's API session. Batches are staged through
the API (``staged_upload``), so their summary first asks for the file's currency;
the matching then lists the default synthetic lines (senders without an address)
as exceptions. An exception opens beside its source row, and no donor is ever
chosen for the reviewer.
"""

from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions
from playwright.sync_api import Locator, Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import ROW_ERROR_MESSAGES, DecisionKind, RowErrorCode
from alma_spei_tests.data import BankRow, BankStatement
from alma_spei_tests.pages import DonorMessages, ReviewMessages, ReviewPage
from alma_spei_tests.steps import imports_steps, review_steps, ui_steps
from alma_spei_tests.testbase import BaseE2ETest

#: Valid rows in the default two-line statement.
STAGED_VALID_ROWS = 2

#: An impossible date, used with a blank sender for an invalid line.
INVALID_DATE = "2026-02-30"
SOME_AMOUNT = "1,00"


@allure.feature("Import review UI")
class TestReviewQueueUi(BaseE2ETest):
    def test_queue_lists_the_staged_import_with_its_progress(
        self, signed_in_page: Page, staged_upload: dict[str, Any]
    ):
        # 1. Stage an upload (fixture)
        # 2. Open the review queue from the navigation
        # 3. Verification: the batch is listed by file name with zero checked transfers
        filename = staged_upload["batch"]["original-filename"]
        review = ui_steps.open_review_queue(signed_in_page)
        item = review.queue_item(filename)
        expect(item).to_have_count(1)
        expect(review.progress_text(item)).to_have_text(
            ReviewMessages.progress(0, STAGED_VALID_ROWS, 0)
        )

    def test_queue_entry_opens_the_batch(self, signed_in_page: Page, staged_upload: dict[str, Any]):
        # 1. Open the review queue
        # 2. Choose the staged batch
        # 3. Verification: the batch's summary, by its deep link, asking for the source
        #    settings the API upload did not give
        batch = staged_upload["batch"]
        review = ui_steps.open_review_queue(signed_in_page)
        review.queue_button(batch["original-filename"]).click()
        ui_steps.wait_for_summary(review, batch["original-filename"])
        expect(review.summary_button(ReviewMessages.RUN_MATCHING)).to_be_visible()
        assert_that(signed_in_page.url).described_as(
            "the batch view should be addressable by a deep link"
        ).ends_with(ReviewMessages.deep_link(batch["id"]))

    def test_the_source_settings_are_confirmed_once(
        self, signed_in_page: Page, staged_upload: dict[str, Any]
    ):
        # 1. Deep-link to a staged batch, confirm PLN and run the matching
        # 2. Reload the page
        # 3. Verification: the summary comes back with its counts and exceptions, without
        #    asking for the settings again
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.run_matching(review)
        signed_in_page.reload()
        ui_steps.wait_for_summary(review, batch["original-filename"])
        expect(review.summary_button(ReviewMessages.RUN_MATCHING)).to_have_count(0)
        expect(review.exception_cards).to_have_count(STAGED_VALID_ROWS)


@allure.feature("Import review UI")
class TestExceptionUi(BaseE2ETest):
    def test_no_donor_is_preselected(
        self,
        signed_in_page: Page,
        api: AlmaSpeiApi,
        staged_upload: dict[str, Any],
        bank_statement: BankStatement,
    ):
        # 1. Deep-link to a staged batch, run the matching and explain row 2
        # 2. Verification: no donor is chosen and no payment question is asked; the reviewer
        #    is offered the catalogue or a new donor; the row stays unresolved
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.run_matching(review)
        ui_steps.explain_exception(review, 2, bank_statement.rows[1].sender)
        expect(review.chosen_donor).to_have_count(0)
        expect(review.payment_form).to_have_count(0)
        expect(review.choice_button(ReviewMessages.FROM_CATALOGUE)).to_be_enabled()
        expect(review.choice_button(ReviewMessages.NEW_DONOR)).to_be_enabled()
        decision = review_steps.read_decision(api, batch["id"], 2).json()["decision"]
        assert_that(decision["kind"]).described_as(
            "explaining a row should not choose anything by itself"
        ).is_equal_to(DecisionKind.UNRESOLVED)

    def test_comparison_shows_the_source_row_beside_the_chosen_donor(
        self,
        signed_in_page: Page,
        staged_upload: dict[str, Any],
        bank_statement: BankStatement,
        donor: dict[str, Any],
        tag: str,
    ):
        # 1. Deep-link to a staged batch, run the matching and explain row 2
        # 2. Search the catalogue by this test's tag and compare with the tagged donor
        # 3. Verification: the source card shows row 2's raw values and an unknown currency;
        #    the donor card shows the donor's type, name, city and active status
        batch = staged_upload["batch"]
        source = bank_statement.rows[1]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.run_matching(review)
        ui_steps.explain_exception(review, 2, source.sender)
        ui_steps.look_up_donors(review)
        ui_steps.compare_with_donor(review, tag, donor["name"], donor["city"])
        with soft_assertions():
            assert_that(card_values(review, review.source_card, SOURCE_LABELS)).described_as(
                "the source card should show the row as written in the file"
            ).is_equal_to(
                {
                    ReviewMessages.SOURCE_DATE: source.date_text,
                    ReviewMessages.SOURCE_SENDER: source.sender,
                    ReviewMessages.SOURCE_DESCRIPTION: source.description,
                    ReviewMessages.SOURCE_AMOUNT: source.amount,
                    ReviewMessages.CURRENCY: ReviewMessages.UNKNOWN_CURRENCY,
                }
            )
            assert_that(card_values(review, review.donor_card, DONOR_LABELS)).described_as(
                "the donor card should show the chosen donor's current profile"
            ).is_equal_to(
                {
                    ReviewMessages.DONOR_TYPE: DonorMessages.ENTITY_LABELS[donor["entity-type"]],
                    ReviewMessages.DONOR_NAME: donor["name"],
                    ReviewMessages.DONOR_CITY: donor["city"],
                    ReviewMessages.DONOR_STATUS: ReviewMessages.ACTIVE,
                }
            )

    def test_invalid_row_shows_its_errors_beside_the_comparison(
        self, signed_in_page: Page, api_staged_invalid: dict[str, Any]
    ):
        # 1. Stage a statement whose second line is invalid (fixture)
        # 2. Deep-link to it, run the matching and explain the invalid row
        # 3. Verification: the alert that choosing a donor fixes nothing, and the source card's
        #    notice with the Polish reasons
        batch = api_staged_invalid["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.run_matching(review)
        ui_steps.explain_exception(review, 2, ReviewMessages.REASONS["invalid-row"])
        expect(review.invalid_row_alert).to_have_text(ReviewMessages.INVALID_ROW_ALERT)
        expect(review.source_card).to_contain_text(ReviewMessages.INVALID_ROW_NOTICE)
        expect(review.source_card.locator("li")).to_have_text(
            [
                ROW_ERROR_MESSAGES[RowErrorCode.INVALID_DATE],
                ROW_ERROR_MESSAGES[RowErrorCode.MISSING_SENDER],
            ]
        )


# --- file-local fixtures and helpers ------------------------------------------
SOURCE_LABELS = (
    ReviewMessages.SOURCE_DATE,
    ReviewMessages.SOURCE_SENDER,
    ReviewMessages.SOURCE_DESCRIPTION,
    ReviewMessages.SOURCE_AMOUNT,
    ReviewMessages.CURRENCY,
)
DONOR_LABELS = (
    ReviewMessages.DONOR_TYPE,
    ReviewMessages.DONOR_NAME,
    ReviewMessages.DONOR_CITY,
    ReviewMessages.DONOR_STATUS,
)


@pytest.fixture
def api_staged_invalid(api: AlmaSpeiApi, bank_statement: BankStatement, tag: str) -> dict[str, Any]:
    """A staged statement: one valid line, then one with a bad date and no sender."""
    invalid = BankRow(INVALID_DATE, "", tag, SOME_AMOUNT)
    statement = BankStatement([bank_statement.rows[0], invalid])
    return imports_steps.upload_staged(api, f"{tag}.csv", statement.to_csv())


def card_values(review: ReviewPage, card: Locator, labels: tuple[str, ...]) -> dict[str, str]:
    return {label: review.card_value(card, label).inner_text().strip() for label in labels}
