"""API tests for the master donor workbook and the 1.5% tax list (tasks 65-67).

``POST /api/imports/upload`` takes ``source=master`` and ``source=tax`` beside
``bank``. Both new sources stage every data row with its source location and stop
there: nothing reaches the donor or payment tables, the bank review and commit
workflow ignores them, and the byte-identical-file refusal spans all sources.

* master: the full name stays one field; columns G-X are kept as source
  observations (G-K with their year), the summary column Y is never kept, and a
  filled Z flags the row because its meaning is unknown;
* tax: rows 1-2 are titles, row 3 the checked header, data from row 4; the
  taxpayer and the spouse are kept apart, the amount is an exact decimal text,
  and an anonymous declaration (no personal data) is valid.
"""

from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error_includes, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import IMPORT_PAGE_MAX_LIMIT, ImportErrorPayload, ImportSource
from alma_spei_tests.data.sources import (
    MASTER_HEADER,
    TAX_FIRST_DATA_ROW,
    TAX_HEADER,
    MasterRow,
    TaxRow,
    TaxSubject,
    master_csv,
    master_xlsx,
    tax_csv,
    tax_xlsx,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, imports_steps
from alma_spei_tests.testbase import BaseApiTest

MASTER_VERSIONS = ("master-parser-v1", "master-observations-v1")
TAX_VERSIONS = ("tax-parser-v1", "tax-designation-v1")

#: Validation codes of the new sources (contracts/imports.cljc ``row-messages``).
INVALID_MASTER_NAME = "invalid-master-name"
INVALID_MASTER_PROFILE = "invalid-master-profile"
INVALID_MASTER_OBSERVATION = "invalid-master-observation"
UNEXPECTED_MASTER_COLUMN = "unexpected-master-column"
INVALID_TAXPAYER = "invalid-taxpayer"
INVALID_TAX_AMOUNT = "invalid-tax-amount"

#: Column indexes (0-based) of the master name, its first observation (G) and summary (Y).
NAME, FIRST_YEAR, SUMMARY = 0, 6, 24
#: Column indexes (0-based) of the tax list's taxpayer first name and amount.
TAXPAYER_FIRST_NAME, TAX_AMOUNT = 1, 8


@allure.feature("Master and tax imports")
class TestMasterWorkbook(BaseApiTest):
    def test_a_master_workbook_is_staged_with_its_profile_and_observations(
        self, api: AlmaSpeiApi, db: DbQueries, tag: str
    ):
        # 1. Upload a master CSV with one donor (years, the 1.5% column, a summary)
        # 2. Verification: a master batch with the source's versions; the donor's full name
        #    as one field, the profile, and the G-X observations (G-K with their year,
        #    never the summary); the staged row carries the mapping version; the donor
        #    and payment tables are unchanged
        row = MasterRow(name=f"Anna Maria Testowa {tag}")
        before = db_steps.read_canonical_counts(db)
        body = imports_steps.upload_staged(
            api, f"{tag}.csv", master_csv([row]), source=ImportSource.MASTER
        )
        staged = db_steps.read_staged_rows(db, body["batch"]["id"])
        with soft_assertions():
            assert_that(
                (
                    body["batch"]["source-type"],
                    body["batch"]["parse-version"],
                    body["batch"]["mapping-version"],
                )
            ).described_as("the batch should be a staged master import").is_equal_to(
                (ImportSource.MASTER, *MASTER_VERSIONS)
            )
            assert_that(body["rows"][0]["payload"]).described_as(
                "the full name should stay one field, next to the observations"
            ).is_equal_to(
                {
                    "name": row.name,
                    "street": row.street,
                    "postal-code": row.postal_code,
                    "city": row.city,
                    "province": row.province,
                    "gender": row.gender,
                    "observations": row.expected_observations(),
                }
            )
            assert_that([(r["row_number"], r["rule_version"]) for r in staged]).described_as(
                "the row should be staged at its sheet row with the master mapping"
            ).is_equal_to([(2, MASTER_VERSIONS[1])])
            assert_that(db_steps.read_canonical_counts(db)).described_as(
                "yearly figures should never become donors or payments"
            ).is_equal_to(before)

    def test_xlsx_numbers_are_kept_as_number_observations(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a master XLSX whose year columns are numbers
        # 2. Verification: the year observations are typed "number" and keep their values
        row = MasterRow(name=f"Jan Liczbowy {tag}", observations=("10", "20", "30", "40", "50"))
        numbers = frozenset(range(FIRST_YEAR, FIRST_YEAR + 5))
        body = imports_steps.upload_staged(
            api,
            f"{tag}.xlsx",
            master_xlsx([row.cells()], numbers=numbers),
            separator=None,
            source=ImportSource.MASTER,
        )
        assert_that(body["rows"][0]["payload"]["observations"]).described_as(
            "numeric year cells should be number observations"
        ).is_equal_to(row.expected_observations("number"))

    @pytest.mark.parametrize(
        ("kind", "code"),
        [
            pytest.param("blank-name", INVALID_MASTER_NAME, id="blank-name"),
            pytest.param("filled-z", UNEXPECTED_MASTER_COLUMN, id="filled-z"),
            pytest.param("number-name", INVALID_MASTER_PROFILE, id="number-in-name"),
            pytest.param("date-observation", INVALID_MASTER_OBSERVATION, id="date-observation"),
        ],
    )
    def test_a_doubtful_master_row_is_staged_invalid_with_its_reason(
        self, api: AlmaSpeiApi, tag: str, kind: str, code: str
    ):
        # 1. Upload a master XLSX whose only donor row has one doubtful cell
        # 2. Verification: the row is staged invalid with exactly that reason - nothing is
        #    guessed or dropped
        doubtful, numbers, dates = doubtful_master_row(kind, tag)
        content = master_xlsx([doubtful], numbers=numbers, dates=dates)
        body = imports_steps.upload_staged(
            api, f"{tag}.xlsx", content, separator=None, source=ImportSource.MASTER
        )
        assert_that([(r["row-number"], codes_of(r)) for r in body["rows"]]).described_as(
            f"the {kind} row should be flagged with its reason"
        ).is_equal_to([(2, [code])])

    @pytest.mark.parametrize(
        "column", [0, 6, 11, 24], ids=["name-heading", "year-heading", "1.5-heading", "summary"]
    )
    def test_a_master_file_with_another_header_is_refused(
        self, api: AlmaSpeiApi, tag: str, column: int
    ):
        # 1. Upload a master CSV whose header has one heading replaced
        # 2. Verification: 400 invalid structure - the columns are never guessed
        header = list(MASTER_HEADER)
        header[column] = "Kolumna"
        content = master_csv([MasterRow(name=f"Jan {tag}")], header=header)
        response = imports_steps.upload(api, f"{tag}.csv", content, source=ImportSource.MASTER)
        assert_error_includes(
            response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
        )

    def test_the_original_summary_formula_is_refused(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a master XLSX whose summary cell is a formula
        # 2. Verification: 400 unsupported format - only a values-only copy is read
        row = MasterRow(name=f"Jan Formułowy {tag}").cells()
        content = master_xlsx([row], formulas={SUMMARY: "SUM(G2:K2)"})
        response = imports_steps.upload(
            api, f"{tag}.xlsx", content, separator=None, source=ImportSource.MASTER
        )
        assert_error_includes(
            response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.UNSUPPORTED_FORMAT
        )


@allure.feature("Master and tax imports")
class TestTaxList(BaseApiTest):
    def test_a_tax_list_is_staged_from_row_four_with_separate_people(
        self, api: AlmaSpeiApi, db: DbQueries, tag: str
    ):
        # 1. Upload a tax CSV: titles, header, a taxpayer with a spouse at the same address,
        #    and an anonymous declaration
        # 2. Verification: a tax batch; rows from 4 on; the taxpayer and the spouse are two
        #    separate subjects, the purpose is kept and the amount is a dot decimal; the
        #    anonymous row is valid without personal data; nothing canonical changes
        address = f"ul. Polna 2, 30-002 Kraków {tag}"
        couple = TaxRow(
            "1",
            TaxSubject("Jan", f"Podatnik {tag}", address),
            TaxSubject("Anna", f"Podatnik {tag}", address),
            purpose="Hospicjum - cel szczegółowy",
            amount="12,50",
        )
        anonymous = TaxRow("2", amount="7,05")
        before = db_steps.read_canonical_counts(db)
        body = imports_steps.upload_staged(
            api, f"{tag}.csv", tax_csv([couple, anonymous]), source=ImportSource.TAX
        )
        with soft_assertions():
            assert_that(
                (
                    body["batch"]["source-type"],
                    body["batch"]["parse-version"],
                    body["batch"]["mapping-version"],
                )
            ).described_as("the batch should be a staged tax import").is_equal_to(
                (ImportSource.TAX, *TAX_VERSIONS)
            )
            assert_that(
                [(r["row-number"], r["validation-state"]) for r in body["rows"]]
            ).described_as("data should start at row 4 and both rows be valid").is_equal_to(
                [(TAX_FIRST_DATA_ROW, "valid"), (TAX_FIRST_DATA_ROW + 1, "valid")]
            )
            assert_that([r["payload"] for r in body["rows"]]).described_as(
                "the taxpayer and the spouse should stay apart, the amount exact"
            ).is_equal_to(
                [
                    {
                        "taxpayer": couple.taxpayer.payload(),
                        "spouse": couple.spouse.payload(),
                        "purpose": couple.purpose,
                        "amount": "12.50",
                    },
                    {"amount": "7.05"},
                ]
            )
            assert_that(db_steps.read_canonical_counts(db)).described_as(
                "a tax list should not create donors or payments"
            ).is_equal_to(before)

    def test_an_xlsx_amount_is_kept_as_an_exact_decimal(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a tax XLSX whose amount is a number cell
        # 2. Verification: the amount is its plain decimal text
        row = TaxRow("1", TaxSubject("Ewa", f"Liczbowa {tag}"), amount="1234.5")
        body = imports_steps.upload_staged(
            api,
            f"{tag}.xlsx",
            tax_xlsx([row.cells()], numbers=frozenset({TAX_AMOUNT})),
            separator=None,
            source=ImportSource.TAX,
        )
        assert_that(body["rows"][0]["payload"]["amount"]).described_as(
            "a numeric amount should be kept exactly"
        ).is_equal_to("1234.5")

    @pytest.mark.parametrize(
        ("amount", "numbers"),
        [
            pytest.param("abc", frozenset(), id="text"),
            pytest.param("-5,00", frozenset(), id="negative-text"),
            pytest.param("", frozenset(), id="empty"),
            pytest.param("-5", frozenset({TAX_AMOUNT}), id="negative-number"),
        ],
    )
    def test_a_wrong_amount_is_staged_invalid(
        self, api: AlmaSpeiApi, tag: str, amount: str, numbers: frozenset[int]
    ):
        # 1. Upload a tax XLSX whose only row has a wrong amount
        # 2. Verification: the row is invalid with the amount reason, and no amount is kept
        row = TaxRow("1", TaxSubject("Jan", f"Kwotowy {tag}"), amount=amount)
        body = imports_steps.upload_staged(
            api,
            f"{tag}.xlsx",
            tax_xlsx([row.cells()], numbers=numbers),
            separator=None,
            source=ImportSource.TAX,
        )
        assert_that((codes_of(body["rows"][0]), body["rows"][0]["payload"]["amount"])).described_as(
            "a wrong amount should be flagged, never guessed"
        ).is_equal_to(([INVALID_TAX_AMOUNT], None))

    def test_a_number_in_a_name_field_is_flagged(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a tax XLSX whose taxpayer first name is a number cell
        # 2. Verification: the row is invalid for the taxpayer
        row = TaxRow("1", TaxSubject("123", f"Numer {tag}"))
        body = imports_steps.upload_staged(
            api,
            f"{tag}.xlsx",
            tax_xlsx([row.cells()], numbers=frozenset({TAXPAYER_FIRST_NAME})),
            separator=None,
            source=ImportSource.TAX,
        )
        assert_that(codes_of(body["rows"][0])).described_as("a number is not a name").is_equal_to(
            [INVALID_TAXPAYER]
        )

    @pytest.mark.parametrize("variant", ["wrong-heading", "no-title-lines"])
    def test_a_tax_file_without_its_header_at_row_three_is_refused(
        self, api: AlmaSpeiApi, tag: str, variant: str
    ):
        # 1. Upload a tax CSV with a changed heading, or without the two title lines
        # 2. Verification: 400 invalid structure
        row = TaxRow("1", TaxSubject("Jan", f"Nagłówek {tag}"))
        if variant == "wrong-heading":
            header = list(TAX_HEADER)
            header[-1] = "Kwota"
            content = tax_csv([row], header=header)
        else:
            content = tax_csv([row]).split(b"\n", 2)[2]
        response = imports_steps.upload(api, f"{tag}.csv", content, source=ImportSource.TAX)
        assert_error_includes(
            response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
        )


@allure.feature("Master and tax imports")
class TestSourceRouting(BaseApiTest):
    @pytest.mark.parametrize("other", [ImportSource.TAX, ImportSource.BANK])
    def test_the_same_bytes_are_refused_as_another_source(
        self, api: AlmaSpeiApi, tag: str, other: str
    ):
        # 1. Stage a master file
        # 2. Upload the same bytes, renamed, as another source
        # 3. Verification: 409 duplicate file - before any parsing
        content = master_csv([MasterRow(name=f"Jan Duplikat {tag}")])
        imports_steps.upload_staged(api, f"{tag}.csv", content, source=ImportSource.MASTER)
        response = imports_steps.upload(api, f"{tag}-kopia.csv", content, source=other)
        assert_error_includes(response, HTTPStatus.CONFLICT, ImportErrorPayload.DUPLICATE_FILE)

    def test_a_retry_must_keep_its_source(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a tax file with a wrong header (its batch fails)
        # 2. Retry the same bytes as a master file
        # 3. Verification: 409 retry file mismatch
        header = [*TAX_HEADER[:-1], "Kwota"]
        content = tax_csv([TaxRow("1", TaxSubject("Jan", f"Ponowny {tag}"))], header=header)
        failed = imports_steps.upload(api, f"{tag}.csv", content, source=ImportSource.TAX).json()
        batch = failed["batch"]
        response = imports_steps.retry(
            api, batch["id"], batch["version"], f"{tag}.csv", content, source=ImportSource.MASTER
        )
        assert_error_includes(response, HTTPStatus.CONFLICT, ImportErrorPayload.RETRY_FILE_MISMATCH)

    def test_an_unknown_source_is_refused(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a file as a source that does not exist
        # 2. Verification: 400 invalid structure
        content = master_csv([MasterRow(name=f"Jan Nieznany {tag}")])
        response = imports_steps.upload(api, f"{tag}.csv", content, source="payroll")
        assert_error_includes(
            response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
        )

    @pytest.mark.parametrize("source", [ImportSource.MASTER, ImportSource.TAX])
    def test_a_csv_of_any_source_needs_its_separator(self, api: AlmaSpeiApi, tag: str, source: str):
        # 1. Upload a master or tax CSV without choosing the separator
        # 2. Verification: 400 invalid structure
        content = (
            master_csv([MasterRow(name=f"Jan {tag}")])
            if source == ImportSource.MASTER
            else tax_csv([TaxRow("1", TaxSubject("Jan", tag))])
        )
        response = imports_steps.upload(api, f"{tag}.csv", content, separator=None, source=source)
        assert_error_includes(
            response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
        )

    @pytest.mark.parametrize("source", [ImportSource.MASTER, ImportSource.TAX])
    def test_master_and_tax_batches_stay_out_of_the_bank_review(
        self, api: AlmaSpeiApi, tag: str, source: str
    ):
        # 1. Stage a master or tax file
        # 2. Read the bank review queue and the batch's review view
        # 3. Verification: the batch is not queued, and its review view is not found
        content = (
            master_csv([MasterRow(name=f"Jan Kolejka {tag}")])
            if source == ImportSource.MASTER
            else tax_csv([TaxRow("1", TaxSubject("Jan", f"Kolejka {tag}"))])
        )
        batch = imports_steps.upload_staged(api, f"{tag}.csv", content, source=source)["batch"]
        queue = imports_steps.review_queue(api, limit=IMPORT_PAGE_MAX_LIMIT).json()["batches"]
        review = imports_steps.read_batch(api, batch["id"])
        with soft_assertions():
            assert_that([b["id"] for b in queue]).described_as(
                "the bank review should not list other sources"
            ).does_not_contain(batch["id"])
            assert_status(review, HTTPStatus.NOT_FOUND, "the review view of another source")


# --- file-local helpers -------------------------------------------------------
def codes_of(row: dict[str, Any]) -> list[str]:
    return [error["code"] for error in row["errors"]]


def doubtful_master_row(kind: str, tag: str) -> tuple[list[str], frozenset[int], frozenset[int]]:
    """A master row with one doubtful cell, and which cells are numbers or dates."""
    row = MasterRow(name=f"Jan Wątpliwy {tag}")
    cells = row.cells()
    if kind == "blank-name":
        cells[NAME] = ""
        return cells, frozenset(), frozenset()
    if kind == "filled-z":
        cells[-1] = "nieznane"
        return cells, frozenset(), frozenset()
    if kind == "number-name":
        cells[NAME] = "42"
        return cells, frozenset({NAME}), frozenset()
    cells[FIRST_YEAR] = "46037"
    return cells, frozenset(), frozenset({FIRST_YEAR})
