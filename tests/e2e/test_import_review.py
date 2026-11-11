"""E2E tests for the Polish import review screen (task 37).

The browser borrows the administrator's API session. Batches are staged through
the API (``staged_upload``) unless the upload screen itself is under test.
Rows are picked explicitly; the screen never preselects a donor.
"""

from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions
from playwright.sync_api import Locator, Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import ROW_ERROR_MESSAGES, CsvSeparator, RowErrorCode
from alma_spei_tests.data import BankRow, BankStatement
from alma_spei_tests.pages import DonorMessages, ReviewMessages, ReviewPage
from alma_spei_tests.steps import imports_steps, ui_steps
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
        # 3. Verification: the batch is listed by file name with zero reviewed rows
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
        # 3. Verification: the batch view, headed by the file name, with a deep link in the URL
        batch = staged_upload["batch"]
        review = ui_steps.open_review_queue(signed_in_page)
        review.queue_button(batch["original-filename"]).click()
        expect(review.batch_heading).to_have_text(batch["original-filename"])
        assert_that(signed_in_page.url).described_as(
            "the batch view should be addressable by a deep link"
        ).ends_with(ReviewMessages.deep_link(batch["id"]))

    def test_upload_report_links_to_the_review(
        self, signed_in_page: Page, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload a statement through the upload screen
        # 2. Follow "Przejdź do weryfikacji"
        # 3. Verification: the review of that very batch opens
        filename = f"{tag}.csv"
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(
            imports, filename, bank_statement.to_csv(), CsvSeparator.SEMICOLON
        )
        ui_steps.submit_upload(imports)
        imports.review_link.click()
        expect(ReviewPage(signed_in_page).batch_heading).to_have_text(filename)


@allure.feature("Import review UI")
class TestManualComparisonUi(BaseE2ETest):
    def test_no_donor_is_preselected(self, signed_in_page: Page, staged_upload: dict[str, Any]):
        # 1. Deep-link to a staged batch and pick row 2
        # 2. Verification: the donor card asks for a search - no profile is chosen automatically
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.pick_review_row(review, 2)
        expect(review.donor_card).to_contain_text(ReviewMessages.NO_DONOR_YET)

    def test_comparison_shows_the_source_row_beside_the_chosen_donor(
        self,
        signed_in_page: Page,
        staged_upload: dict[str, Any],
        bank_statement: BankStatement,
        donor: dict[str, Any],
        tag: str,
    ):
        # 1. Deep-link to a staged batch and pick row 2
        # 2. Search donors by this test's tag and compare with the tagged donor
        # 3. Verification: the source card shows row 2's raw values and an unknown currency;
        #    the donor card shows the donor's type, name, city and active status
        batch = staged_upload["batch"]
        source = bank_statement.rows[1]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.pick_review_row(review, 2)
        ui_steps.compare_with_donor(review, tag, donor["name"], donor["city"])
        expect(review.card_value(review.donor_card, ReviewMessages.DONOR_NAME)).to_have_text(
            donor["name"]
        )
        with soft_assertions():
            assert_that(card_values(review, review.source_card, SOURCE_LABELS)).described_as(
                "the source card should show the row as written in the file"
            ).is_equal_to(
                {
                    ReviewMessages.SOURCE_DATE: source.date.isoformat(),
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
            assert_that(review.source_card.inner_text()).described_as(
                "the source card should name the compared row"
            ).contains(ReviewMessages.source_location(2))

    def test_invalid_row_shows_its_errors_beside_the_comparison(
        self, signed_in_page: Page, api_staged_invalid: dict[str, Any]
    ):
        # 1. Stage a statement whose second line is invalid (fixture)
        # 2. Deep-link to it and pick row 2
        # 3. Verification: the notice that comparing fixes nothing, with the Polish reasons
        batch = api_staged_invalid["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.pick_review_row(review, 2)
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
