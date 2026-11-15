"""E2E tests for the Polish bank upload screen and validation report (task 36).

The browser borrows the administrator's API session (``signed_in_page``).
Every uploaded file embeds the test's tag, since the backend refuses a
byte-identical file twice.
"""

from typing import Any

import allure
from assertpy import assert_that, soft_assertions
from playwright.sync_api import Page, expect

from alma_spei_tests.constants import ROW_ERROR_MESSAGES, CsvSeparator, RowErrorCode
from alma_spei_tests.data import BankRow, BankStatement, blank_only_csv, new_bank_statement
from alma_spei_tests.pages import ImportMessages, ImportsPage
from alma_spei_tests.steps import ui_steps
from alma_spei_tests.testbase import BaseE2ETest

#: A non-existent date, blank sender and zero amount: three row errors.
INVALID_ROW = BankRow(date="2026-02-30", sender="", description="", amount="0")

#: A statement one row longer than a report page (25), to exercise paging.
PAGED_ROW_COUNT = 26

#: Rendered for an empty cell in the report.
EMPTY_CELL = "—"


@allure.feature("Bank upload UI")
class TestUploadScreen(BaseE2ETest):
    def test_navigation_opens_the_upload_screen(self, signed_in_page: Page):
        # 1. Open the app with the administrator's session
        # 2. Choose "Import przelewów" in the navigation
        # 3. Verification: the upload screen with its synthetic-data note and a disabled submit
        imports = ui_steps.open_imports(signed_in_page)
        with soft_assertions():
            assert_that(imports.synthetic_note.is_visible()).described_as(
                "the screen should remind to use synthetic data only"
            ).is_true()
            assert_that(imports.upload_button.is_disabled()).described_as(
                "submit should stay disabled until a file is chosen"
            ).is_true()

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

    def test_unsupported_file_type_is_refused_in_the_browser(self, signed_in_page: Page, tag: str):
        # 1. Open the upload screen
        # 2. Choose a .txt file
        # 3. Verification: the Polish file-type alert, and submit stays disabled
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(imports, f"{tag}.txt", tag.encode())
        expect(imports.alert).to_have_text(ImportMessages.WRONG_FILE_TYPE)
        expect(imports.upload_button).to_be_disabled()


@allure.feature("Bank upload UI")
class TestUploadReport(BaseE2ETest):
    def test_csv_upload_shows_the_summary_and_every_row(
        self, signed_in_page: Page, bank_statement: BankStatement, tag: str
    ):
        # 1. Open the upload screen, choose a two-line CSV and the ';' separator
        # 2. Submit it for analysis
        # 3. Verification: the summary reports a batch awaiting review with two valid rows,
        #    and the report lists both rows with Polish decimals and an unknown currency
        filename = f"{tag}.csv"
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(
            imports, filename, bank_statement.to_csv(), CsvSeparator.SEMICOLON
        )
        ui_steps.submit_upload(imports)
        ui_steps.wait_for_import_state(imports, ImportMessages.STATE_REVIEW)
        expect(imports.rows_summary).to_have_text(ImportMessages.rows_summary(1, 2, 2))
        with soft_assertions():
            assert_that(summary_values(imports, SUMMARY_LABELS)).described_as(
                "the summary should describe the staged file"
            ).is_equal_to(
                {
                    ImportMessages.FILE: filename,
                    ImportMessages.ATTEMPT: "1",
                    ImportMessages.TOTAL_ROWS: "2",
                    ImportMessages.VALID_ROWS: "2",
                    ImportMessages.INVALID_ROWS: "0",
                    ImportMessages.SKIPPED_ROWS: "0",
                }
            )
            for number, row in enumerate(bank_statement.rows, start=1):
                assert_that(imports.report_cells(number)).described_as(
                    f"report row {number} should show the parsed values"
                ).is_equal_to(
                    [
                        row.date_text,
                        row.sender,
                        row.description,
                        row.amount,  # Polish comma decimal, as uploaded
                        ImportMessages.UNKNOWN_CURRENCY,
                        ImportMessages.VALID_FORMAT,
                    ]
                )

    def test_invalid_rows_are_listed_with_polish_reasons(
        self, signed_in_page: Page, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload a CSV with one valid line, one line with three problems and a blank line
        # 2. Verification: the invalid-rows notice, the counts, and the bad row's source
        #    values with its three Polish reasons
        statement = BankStatement([bank_statement.rows[0], INVALID_ROW], trailing_blank_lines=1)
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(
            imports, f"{tag}.csv", statement.to_csv(), CsvSeparator.SEMICOLON
        )
        ui_steps.submit_upload(imports)
        ui_steps.wait_for_import_state(imports, ImportMessages.STATE_REVIEW)
        expect(imports.invalid_rows_notice).to_be_visible()
        with soft_assertions():
            assert_that(
                summary_values(
                    imports,
                    (
                        ImportMessages.VALID_ROWS,
                        ImportMessages.INVALID_ROWS,
                        ImportMessages.SKIPPED_ROWS,
                    ),
                )
            ).described_as("the summary should count valid, invalid and skipped rows").is_equal_to(
                {
                    ImportMessages.VALID_ROWS: "1",
                    ImportMessages.INVALID_ROWS: "1",
                    ImportMessages.SKIPPED_ROWS: "1",
                }
            )
            assert_that(imports.report_cells(2)[:4]).described_as(
                "the bad row should show its source date, empty cells and source amount"
            ).is_equal_to([INVALID_ROW.date, EMPTY_CELL, EMPTY_CELL, INVALID_ROW.amount])
            assert_that(imports.report_errors(2)).described_as(
                "the bad row should list its three problems in Polish"
            ).is_equal_to(
                [
                    ROW_ERROR_MESSAGES[RowErrorCode.INVALID_DATE],
                    ROW_ERROR_MESSAGES[RowErrorCode.MISSING_SENDER],
                    ROW_ERROR_MESSAGES[RowErrorCode.INVALID_AMOUNT],
                ]
            )

    def test_xlsx_upload_needs_no_separator(
        self, signed_in_page: Page, bank_statement: BankStatement, tag: str
    ):
        # 1. Open the upload screen and choose an XLSX workbook
        # 2. Submit it for analysis
        # 3. Verification: no separator choice was offered and the batch awaits review
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(imports, f"{tag}.xlsx", bank_statement.to_xlsx())
        expect(imports.separator_select).to_have_count(0)
        ui_steps.submit_upload(imports)
        ui_steps.wait_for_import_state(imports, ImportMessages.STATE_REVIEW)

    def test_report_pages_through_more_rows_than_fit(self, signed_in_page: Page, tag: str):
        # 1. Upload a CSV one row longer than a report page
        # 2. Go to the next rows
        # 3. Verification: 25 rows then the last one, with matching range summaries
        statement = new_bank_statement(tag, rows=PAGED_ROW_COUNT)
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(
            imports, f"{tag}.csv", statement.to_csv(), CsvSeparator.SEMICOLON
        )
        ui_steps.submit_upload(imports)
        expect(imports.rows_summary).to_have_text(
            ImportMessages.rows_summary(1, PAGED_ROW_COUNT - 1, PAGED_ROW_COUNT)
        )
        imports.next_rows_button.click()
        expect(imports.rows_summary).to_have_text(
            ImportMessages.rows_summary(PAGED_ROW_COUNT, PAGED_ROW_COUNT, PAGED_ROW_COUNT)
        )
        expect(imports.report_rows).to_have_count(1)


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
        # 3. Verification: the Polish duplicate alert
        imports = ui_steps.open_imports(signed_in_page)
        ui_steps.choose_import_file(
            imports, f"{tag}-copy.csv", bank_statement.to_csv(), CsvSeparator.SEMICOLON
        )
        ui_steps.submit_upload(imports)
        expect(imports.alert).to_have_text(ImportMessages.DUPLICATE)

    def test_failed_analysis_offers_a_confirmed_retry(self, signed_in_page: Page, tag: str):
        # 1. Upload a CSV without rows
        # 2. Verify the failure alert and status, and that retry needs confirmation
        # 3. Choose the same file again, confirm and retry
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


# --- file-local helpers -------------------------------------------------------
#: Summary rows compared by the CSV report test.
SUMMARY_LABELS = (
    ImportMessages.FILE,
    ImportMessages.ATTEMPT,
    ImportMessages.TOTAL_ROWS,
    ImportMessages.VALID_ROWS,
    ImportMessages.INVALID_ROWS,
    ImportMessages.SKIPPED_ROWS,
)


def summary_values(imports: ImportsPage, labels: tuple[str, ...]) -> dict[str, str]:
    return {label: imports.summary_value(label).inner_text().strip() for label in labels}
