"""API tests for bank statement uploads (task 35): parsing, staging, rejections.

A successful upload reserves a batch, parses the file and stages every row for
review in one go (201). Invalid rows stay visible with Polish error messages;
whole-file problems reject the upload (and mark the reserved batch failed).
"""

import datetime as dt
from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_error_includes, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    BANK_MAPPING_VERSION,
    BANK_PARSE_VERSION,
    IMPORT_FILE_LIMIT_BYTES,
    ROW_ERROR_MESSAGES,
    STAGED_BATCH_VERSION,
    ApiErrorPayload,
    CsvSeparator,
    Header,
    ImportErrorPayload,
    ImportSource,
    ImportState,
    RowErrorCode,
    RowState,
)
from alma_spei_tests.data import BankRow, BankStatement, ProvisionedAccount, blank_only_csv
from alma_spei_tests.steps import auth_steps, imports_steps
from alma_spei_tests.testbase import BaseApiTest

#: A date that does not exist, a blank sender and a zero amount: three row errors.
INVALID_ROW = BankRow(date="2026-02-30", sender="", description="", amount="0")

#: An extension the bank adapter does not support.
UNSUPPORTED_FILENAME_SUFFIX = ".xls"


@allure.feature("Bank import")
class TestCsvUpload(BaseApiTest):
    @pytest.mark.smoke
    def test_csv_upload_stages_every_row_for_review(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload a two-line ';' separated statement
        # 2. Verification: 201, the batch is in review with consistent counts and versions,
        #    authored by the admin, and every row is staged valid with normalised values
        filename = f"{tag}.csv"
        response = imports_steps.upload(api, filename, bank_statement.to_csv())
        body = response.json()
        with soft_assertions():
            assert_status(response, HTTPStatus.CREATED, "uploading a bank CSV")
            assert_that(project(body["batch"], BATCH_FIELDS)).described_as(
                "the batch should be staged for review with consistent counts"
            ).is_equal_to(
                {
                    "state": ImportState.REVIEW,
                    "version": STAGED_BATCH_VERSION,
                    "attempt-number": 1,
                    "source-type": ImportSource.BANK,
                    "original-filename": filename,
                    "parse-version": BANK_PARSE_VERSION,
                    "mapping-version": BANK_MAPPING_VERSION,
                    "total-rows": 2,
                    "valid-rows": 2,
                    "invalid-rows": 0,
                    "reviewed-rows": 0,
                    "failure-code": None,
                }
            )
            assert_that(body["batch"]["created-by"]).described_as(
                "the batch should be authored by the uploading user"
            ).is_equal_to(api.current_user()["id"])
            assert_that(body["skipped-empty-rows"]).described_as(
                "no blank lines should be skipped"
            ).is_equal_to(0)
            assert_staged_rows(body["rows"], bank_statement.rows)

    def test_comma_separated_csv_is_accepted(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Write the statement with ',' as separator (amounts quoted)
        # 2. Upload it declaring separator ','
        # 3. Verification: 201 and the rows parse exactly as with ';'
        statement = BankStatement(bank_statement.rows, separator=CsvSeparator.COMMA)
        response = imports_steps.upload(
            api, f"{tag}.csv", statement.to_csv(), separator=CsvSeparator.COMMA
        )
        with soft_assertions():
            assert_status(response, HTTPStatus.CREATED, "uploading a comma-separated CSV")
            assert_staged_rows(response.json()["rows"], statement.rows)

    def test_polish_dates_and_decimals_are_normalised(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a line dated DD.MM.YYYY with a comma decimal and one ISO-dated with a dot
        # 2. Verification: dates become ISO and amounts dot-decimal, raw text is kept as source
        statement = BankStatement(
            [
                BankRow("03.01.2026", "Nadawca Testowy", f"Wpłata {tag}", "12,3400"),
                BankRow("2026-01-04", "Nadawca Testowy", f"Zwrot {tag}", "-2.50"),
            ]
        )
        rows = imports_steps.upload_staged(api, f"{tag}.csv", statement.to_csv())["rows"]
        assert_that([(r["payload"]["date"], r["payload"]["amount"]) for r in rows]).described_as(
            "dates and amounts should be normalised"
        ).is_equal_to([("2026-01-03", "12.3400"), ("2026-01-04", "-2.50")])

    def test_invalid_rows_stay_visible_with_polish_errors(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload one valid line, one line with three problems and a trailing blank line
        # 2. Verification: 201; the blank line is skipped and counted; the bad line is staged
        #    invalid with the three Polish messages; the batch counts one invalid row
        statement = BankStatement([bank_statement.rows[0], INVALID_ROW], trailing_blank_lines=1)
        body = imports_steps.upload_staged(api, f"{tag}.csv", statement.to_csv())
        invalid = body["rows"][1]
        with soft_assertions():
            assert_that(body["skipped-empty-rows"]).described_as(
                "the blank line should be skipped and counted"
            ).is_equal_to(1)
            assert_that((body["batch"]["valid-rows"], body["batch"]["invalid-rows"])).described_as(
                "the batch should count one valid and one invalid row"
            ).is_equal_to((1, 1))
            assert_that([r["row-number"] for r in body["rows"]]).described_as(
                "no header row should be invented - lines are numbered from 1"
            ).is_equal_to([1, 2])
            assert_that(invalid["validation-state"]).described_as(
                "the bad line should be staged as invalid"
            ).is_equal_to(RowState.INVALID)
            assert_that({e["code"]: e["message"] for e in invalid["errors"]}).described_as(
                "the bad line should list each problem with its Polish message"
            ).is_equal_to(
                {
                    code: ROW_ERROR_MESSAGES[code]
                    for code in (
                        RowErrorCode.INVALID_DATE,
                        RowErrorCode.MISSING_SENDER,
                        RowErrorCode.INVALID_AMOUNT,
                    )
                }
            )


@allure.feature("Bank import")
class TestXlsxUpload(BaseApiTest):
    def test_xlsx_upload_uses_sheet_row_numbers_and_serial_dates(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Build a workbook whose data starts on sheet row 2, with date-styled serial dates
        # 2. Upload it (no separator for XLSX)
        # 3. Verification: 201, rows keep the sheet row numbers, serial dates become ISO dates
        response = imports_steps.upload(
            api, f"{tag}.xlsx", bank_statement.to_xlsx(first_row=2), separator=None
        )
        rows = response.json().get("rows", [])
        with soft_assertions():
            assert_status(response, HTTPStatus.CREATED, "uploading a bank XLSX")
            assert_that([r["row-number"] for r in rows]).described_as(
                "rows should keep their sheet row numbers"
            ).is_equal_to([2, 3])
            assert_that([r["payload"]["date"] for r in rows]).described_as(
                "date-styled serials should become ISO dates"
            ).is_equal_to([iso(row.date) for row in bank_statement.rows])


@allure.feature("Bank import")
class TestUploadRejections(BaseApiTest):
    def test_the_same_bytes_cannot_be_uploaded_twice(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload a statement
        # 2. Upload byte-identical content under another name
        # 3. Verification: 409 duplicate-file
        content = bank_statement.to_csv()
        imports_steps.upload_staged(api, f"{tag}.csv", content)
        response = imports_steps.upload(api, f"{tag}-renamed.csv", content)
        assert_error_includes(response, HTTPStatus.CONFLICT, ImportErrorPayload.DUPLICATE_FILE)

    def test_unsupported_extension_is_rejected(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload statement bytes named *.xls
        # 2. Verification: 415 unsupported-format
        response = imports_steps.upload(
            api, f"{tag}{UNSUPPORTED_FILENAME_SUFFIX}", bank_statement.to_csv()
        )
        assert_error(
            response, HTTPStatus.UNSUPPORTED_MEDIA_TYPE, ImportErrorPayload.UNSUPPORTED_FORMAT
        )

    @pytest.mark.parametrize(
        ("source", "separator", "fields"),
        [
            pytest.param(ImportSource.BANK, None, None, id="csv-without-separator"),
            pytest.param(ImportSource.TAX, CsvSeparator.SEMICOLON, None, id="unsupported-source"),
            pytest.param(
                ImportSource.BANK, CsvSeparator.SEMICOLON, {"extra": "value"}, id="unknown-field"
            ),
        ],
    )
    def test_invalid_upload_form_is_rejected(
        self,
        api: AlmaSpeiApi,
        bank_statement: BankStatement,
        tag: str,
        source: str,
        separator: CsvSeparator | None,
        fields: dict[str, str] | None,
    ):
        # 1. Upload a valid statement with one form field missing, wrong or unknown
        # 2. Verification: 400 invalid-structure
        response = imports_steps.upload(
            api,
            f"{tag}.csv",
            bank_statement.to_csv(),
            source=source,
            separator=separator,
            fields=fields,
        )
        assert_error_includes(
            response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
        )

    def test_empty_file_is_rejected(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a zero-byte CSV
        # 2. Verification: 400 empty-file
        response = imports_steps.upload(api, f"{tag}.csv", b"")
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.EMPTY_FILE)

    def test_file_without_rows_fails_its_batch(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a CSV with only whitespace lines (unique to this test)
        # 2. Verification: 400 invalid-structure, and the reported batch is failed with that code
        response = imports_steps.upload(api, f"{tag}.csv", blank_only_csv(tag))
        batch = response.json().get("batch", {})
        with soft_assertions():
            assert_error_includes(
                response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
            )
            assert_that((batch.get("state"), batch.get("failure-code"))).described_as(
                "the reserved batch should be marked failed with the rejection code"
            ).is_equal_to((ImportState.FAILED, ImportErrorPayload.INVALID_STRUCTURE["code"]))

    def test_file_over_the_size_limit_is_rejected(self, api: AlmaSpeiApi, tag: str):
        # 1. Build a CSV one byte over the 5 MiB file limit
        # 2. Upload it
        # 3. Verification: 413 resource-limit
        content = tag.encode() + b"x" * (IMPORT_FILE_LIMIT_BYTES + 1 - len(tag))
        response = imports_steps.upload(api, f"{tag}.csv", content)
        assert_error_includes(
            response, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, ImportErrorPayload.RESOURCE_LIMIT
        )


@allure.feature("Bank import")
class TestUploadAuthorization(BaseApiTest):
    def test_anonymous_upload_is_refused(
        self, anonymous_api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload a statement without signing in (CSRF cookie and header present)
        # 2. Verification: 401 unauthenticated
        response = imports_steps.upload(anonymous_api, f"{tag}.csv", bank_statement.to_csv())
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)

    @pytest.mark.parametrize(
        "headers",
        [
            pytest.param({Header.CSRF_TOKEN: None}, id="no-csrf-header"),
            pytest.param({Header.ORIGIN: "http://evil.example"}, id="foreign-origin"),
        ],
    )
    def test_upload_without_csrf_protection_is_forbidden(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str, headers: dict
    ):
        # 1. Upload a statement from the signed-in session with a CSRF requirement broken
        # 2. Verification: 403 csrf
        response = imports_steps.upload(api, f"{tag}.csv", bank_statement.to_csv(), headers=headers)
        assert_error(response, HTTPStatus.FORBIDDEN, ApiErrorPayload.CSRF)

    def test_temporary_password_blocks_uploads(
        self,
        anonymous_api: AlmaSpeiApi,
        staff: ProvisionedAccount,
        bank_statement: BankStatement,
        tag: str,
    ):
        # 1. Log in with a temporary password
        # 2. Upload a statement
        # 3. Verification: 403 password-change-required
        auth_steps.login(anonymous_api, staff.username, staff.temporary_password)
        response = imports_steps.upload(anonymous_api, f"{tag}.csv", bank_statement.to_csv())
        assert_error(response, HTTPStatus.FORBIDDEN, ApiErrorPayload.PASSWORD_CHANGE_REQUIRED)


# --- file-local data and helpers ----------------------------------------------
#: Batch fields compared by the staging test (ids and timestamps vary).
BATCH_FIELDS = (
    "state",
    "version",
    "attempt-number",
    "source-type",
    "original-filename",
    "parse-version",
    "mapping-version",
    "total-rows",
    "valid-rows",
    "invalid-rows",
    "reviewed-rows",
    "failure-code",
)


def project(mapping: dict, fields: tuple[str, ...]) -> dict:
    return {field: mapping.get(field) for field in fields}


def iso(value: str | dt.date) -> str:
    return value.isoformat() if isinstance(value, dt.date) else value


def assert_staged_rows(rows: list[dict[str, Any]], expected: list[BankRow]):
    """Rows are numbered from 1, valid, and carry normalised + source values."""
    assert_that([project(r, ("row-number", "validation-state")) for r in rows]).described_as(
        "every line should be staged valid in file order"
    ).is_equal_to(
        [{"row-number": i, "validation-state": RowState.VALID} for i in range(1, len(expected) + 1)]
    )
    assert_that([r["payload"] for r in rows]).described_as(
        "each staged payload should hold the normalised and the source values"
    ).is_equal_to(
        [
            {
                "date": iso(row.date),
                "sender": row.sender,
                "description": row.description,
                "amount": row.amount.replace(",", "."),
                "currency": None,
                "source-date": iso(row.date),
                "source-amount": row.amount,
            }
            for row in expected
        ]
    )
