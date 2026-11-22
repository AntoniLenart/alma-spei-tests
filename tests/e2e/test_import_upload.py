"""E2E tests for the Polish bank upload screen (task 36, automatic reconciliation).

The browser borrows the administrator's API session (``signed_in_page``).
Every uploaded file embeds the test's tag, since the backend refuses a
byte-identical file twice. The file's currency is confirmed once in the form; a
successful upload goes straight to the import summary, where senders without an
address (the default synthetic lines) and invalid lines are listed as exceptions.
"""

import re
from typing import Any

import allure
from assertpy import assert_that, soft_assertions
from playwright.sync_api import Page, expect

from alma_spei_tests.constants import REVIEW_CURRENCY, CsvSeparator
from alma_spei_tests.data import BankRow, BankStatement, blank_only_csv, new_bank_statement
from alma_spei_tests.pages import ImportMessages, ReviewMessages, ReviewPage
from alma_spei_tests.steps import ui_steps
from alma_spei_tests.testbase import BaseE2ETest

#: A non-existent date, blank sender and zero amount: three row errors.
INVALID_ROW = BankRow(date="2026-02-30", sender="", description="", amount="0")

#: A statement one row longer than a page of exceptions (25), to exercise paging.
PAGED_ROW_COUNT = 26
EXCEPTIONS_PAGE = 25

#: The address of a batch's summary, whatever its id.
SUMMARY_URL = re.compile(r"#review/[0-9a-f-]{36}/0$")

SENDER_FORMAT = ReviewMessages.REASONS["sender-format"]
INVALID_ROW_REASON = ReviewMessages.REASONS["invalid-row"]


@allure.feature("Bank upload UI")
class TestUploadScreen(BaseE2ETest):
    def test_navigation_opens_the_upload_screen(self, signed_in_page: Page):
        # 1. Open the app with the administrator's session
        # 2. Choose "Nowy import" in the sidebar
        # 3. Verification: the upload screen with its synthetic-data note and a disabled submit
        imports = ui_steps.open_imports(signed_in_page)
        with soft_assertions():
            assert_that(imports.synthetic_note.is_visible()).described_as(
                "the screen should remind to use synthetic data only"
            ).is_true()
            assert_that(imports.upload_button.is_disabled()).described_as(
                "submit should stay disabled until a file is chosen"
            ).is_true()

    def test_the_import_steps_follow_the_upload(
        self, signed_in_page: Page, bank_statement: BankStatement, tag: str
    ):
        # 1. Open the upload screen
        # 2. Verify the five import steps, with "Plik" as the current one
        # 3. Upload a valid statement in PLN
        # 4. Verification: the import summary opens with "Dopasowanie" as the current step,
        #    since its senders still need a decision
        filename = f"{tag}.csv"
        imports = ui_steps.open_imports(signed_in_page)
        expect(imports.step_labels).to_have_text(list(ImportMessages.STEPS))
        expect(imports.current_step).to_contain_text(ImportMessages.STEPS[0])
        ui_steps.choose_import_file(
            imports, filename, bank_statement.to_csv(), CsvSeparator.SEMICOLON
        )
        ui_steps.submit_upload(imports)
        review = ui_steps.wait_for_summary(ReviewPage(signed_in_page), filename)
        expect(review.current_step).to_contain_text(ImportMessages.STEPS[2])

    def test_csv_needs_a_separator_before_it_can_be_sent(
        self, signed_in_page: Page, bank_statement: BankStatement, tag: str
    ):
        # 1. Open the upload screen and choose a CSV file
        # 2. Check the submit button, then choose the ';' separator
        # 3. Verification: submit is disabled without a separator and enabled with one
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(imports, f"{tag}.csv", bank_statement.to_csv())
        expect(imports.upload_button).to_be_disabled()
        imports.choose_separator(CsvSeparator.SEMICOLON)
        expect(imports.upload_button).to_be_enabled()

    def test_the_currency_must_be_confirmed_before_sending(
        self, signed_in_page: Page, bank_statement: BankStatement, tag: str
    ):
        # 1. Open the upload screen, choose a CSV file and the ';' separator
        # 2. Submit it without confirming the currency
        # 3. Verification: the browser holds the form back on the missing currency and the
        #    upload screen stays open
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(
            imports, f"{tag}.csv", bank_statement.to_csv(), CsvSeparator.SEMICOLON
        )
        imports.upload_button.click()
        expect(imports.heading).to_be_visible()
        assert_that(
            imports.currency_input.evaluate("input => input.validity.valueMissing")
        ).described_as("the currency should be required before the file is sent").is_true()

    def test_unsupported_file_type_is_refused_in_the_browser(self, signed_in_page: Page, tag: str):
        # 1. Open the upload screen
        # 2. Choose a .txt file
        # 3. Verification: the Polish file-type alert, and submit stays disabled
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(imports, f"{tag}.txt", tag.encode())
        expect(imports.alert).to_have_text(ImportMessages.WRONG_FILE_TYPE)
        expect(imports.upload_button).to_be_disabled()


@allure.feature("Bank upload UI")
class TestUploadSummary(BaseE2ETest):
    def test_a_csv_upload_opens_its_automatic_summary(
        self, signed_in_page: Page, bank_statement: BankStatement, tag: str
    ):
        # 1. Open the upload screen, choose a two-line CSV and the ';' separator
        # 2. Confirm PLN and submit it
        # 3. Verification: the batch's summary opens by its own address; nothing is matched
        #    or prepared yet, and both senders without an address are listed as exceptions
        #    with their date, amount and reason
        filename = f"{tag}.csv"
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(
            imports, filename, bank_statement.to_csv(), CsvSeparator.SEMICOLON
        )
        ui_steps.submit_upload(imports)
        review = ui_steps.wait_for_summary(ReviewPage(signed_in_page), filename)
        expect(signed_in_page).to_have_url(SUMMARY_URL)
        with soft_assertions():
            assert_that(review.count_values()).described_as(
                "nothing should be matched or prepared for senders without an address"
            ).is_equal_to(ReviewMessages.counts(exceptions=len(bank_statement.rows)))
            assert_that(review.exception_texts()).described_as(
                "each line should be listed as an exception with its date, amount and reason"
            ).is_equal_to(
                [
                    [row.sender, f"{row.date_text} · {row.amount} {REVIEW_CURRENCY}", SENDER_FORMAT]
                    for row in bank_statement.rows
                ]
            )

    def test_invalid_rows_are_listed_with_their_reason(
        self, signed_in_page: Page, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload a CSV with one valid line, one line with three problems and a blank line
        # 2. Verification: two exceptions - the valid line for its sender, the bad line for
        #    its source errors; the blank line is not listed
        filename = f"{tag}.csv"
        statement = BankStatement([bank_statement.rows[0], INVALID_ROW], trailing_blank_lines=1)
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(imports, filename, statement.to_csv(), CsvSeparator.SEMICOLON)
        ui_steps.submit_upload(imports)
        review = ui_steps.wait_for_summary(ReviewPage(signed_in_page), filename)
        reasons = [texts[-1] for texts in review.exception_texts()]
        assert_that(reasons).described_as(
            "the valid line and the bad line should be explained in Polish"
        ).is_equal_to([SENDER_FORMAT, INVALID_ROW_REASON])

    def test_xlsx_upload_needs_no_separator(
        self, signed_in_page: Page, bank_statement: BankStatement, tag: str
    ):
        # 1. Open the upload screen and choose an XLSX workbook
        # 2. Confirm PLN and submit it
        # 3. Verification: no separator choice was offered and the batch's summary opens
        filename = f"{tag}.xlsx"
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(imports, filename, bank_statement.to_xlsx())
        expect(imports.separator_select).to_have_count(0)
        ui_steps.submit_upload(imports)
        ui_steps.wait_for_summary(ReviewPage(signed_in_page), filename)

    def test_the_exceptions_page_through_more_rows_than_fit(self, signed_in_page: Page, tag: str):
        # 1. Upload a CSV one row longer than a page of exceptions
        # 2. Go to the next exceptions
        # 3. Verification: all rows are counted as exceptions; 25 cards, then the last one
        filename = f"{tag}.csv"
        statement = new_bank_statement(tag, rows=PAGED_ROW_COUNT)
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(imports, filename, statement.to_csv(), CsvSeparator.SEMICOLON)
        ui_steps.submit_upload(imports)
        review = ui_steps.wait_for_summary(ReviewPage(signed_in_page), filename)
        expect(review.exceptions_pager).to_contain_text(
            ReviewMessages.exceptions_count(PAGED_ROW_COUNT)
        )
        expect(review.exception_cards).to_have_count(EXCEPTIONS_PAGE)
        review.summary_button(ReviewMessages.NEXT_EXCEPTIONS).click()
        expect(review.exception_cards).to_have_count(PAGED_ROW_COUNT - EXCEPTIONS_PAGE)
        expect(review.exception_card(statement.rows[-1].sender)).to_be_visible()


@allure.feature("Bank upload UI")
class TestUploadFailures(BaseE2ETest):
    def test_duplicate_file_is_explained(
        self,
        signed_in_page: Page,
        bank_statement: BankStatement,
        staged_upload: dict[str, Any],
        tag: str,
    ):
        # 1. Stage a statement through the API (fixture)
        # 2. Upload the same bytes through the screen under another name
        # 3. Verification: the Polish duplicate alert, with a way to the import history
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(
            imports, f"{tag}-copy.csv", bank_statement.to_csv(), CsvSeparator.SEMICOLON
        )
        ui_steps.submit_upload(imports)
        expect(imports.alert_message).to_have_text(ImportMessages.DUPLICATE)
        expect(imports.history_link).to_be_visible()

    def test_failed_analysis_offers_a_confirmed_retry(self, signed_in_page: Page, tag: str):
        # 1. Upload a CSV without rows
        # 2. Verify the failure alert and status, and that retry needs confirmation
        # 3. Choose the same file again, confirm the currency and the retry, and retry
        # 4. Verification: the summary moves to attempt 2 (which fails again for these bytes)
        content = blank_only_csv(tag)
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(imports, f"{tag}.csv", content, CsvSeparator.SEMICOLON)
        ui_steps.submit_upload(imports)
        expect(imports.alert).to_have_text(ImportMessages.INVALID_FILE)
        ui_steps.wait_for_import_state(imports, ImportMessages.STATE_FAILED)
        imports.choose_file(f"{tag}.csv", content)
        expect(imports.retry_button).to_be_disabled()
        ui_steps.retry_upload(imports, f"{tag}.csv", content)
        expect(imports.summary_value(ImportMessages.ATTEMPT)).to_have_text("2")
