"""Negative cases of ``docs/negative-import-cases.md`` carried over to the master
workbook and the 1.5% tax list (tasks 66-67).

The new adapters share the bank adapter's readers and limits, so a broken file
of either source must also be refused as a whole with a Polish message or
staged with every row reported - never a server error, and never a write to
the donor or payment tables.
"""

from collections.abc import Callable
from http import HTTPStatus

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error_includes
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import CsvSeparator, ImportErrorPayload, ImportSource
from alma_spei_tests.data.sources import (
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

#: The longest cell the readers accept.
CELL_LIMIT = 4096
POLISH = "Zażółć Gęślą"
#: A merged range in a sheet (unsupported).
MERGED_CELLS = "<mergeCells count='1'><mergeCell ref='B2:C2'/></mergeCells>"
#: The filed bug: a file ending with a lone CR gets a phantom invalid row.
TRAILING_CR_BUG = "a trailing CR is read back as U+FFFF and staged as an extra row; filed as a bug"


def master_file(
    tag: str, *, name: str = "", street: str = MasterRow.street, city: str = MasterRow.city
) -> MasterRow:
    return MasterRow(name=name or f"Jan Negatywny {tag}", street=street, city=city)


def tax_file(tag: str, surname: str = "") -> TaxRow:
    return TaxRow("1", TaxSubject("Jan", surname or f"Negatywny {tag}"))


#: (case, source, extension, builder, expected status, payload)
CASES: list[tuple[str, str, str, Callable[[str], bytes], HTTPStatus, dict[str, str]]] = [
    (
        "windows-1250",
        ImportSource.MASTER,
        "csv",
        lambda t: master_csv([master_file(t, name=f"{POLISH} {t}")]).decode().encode("cp1250"),
        HTTPStatus.BAD_REQUEST,
        ImportErrorPayload.PARSE_FAILED,
    ),
    (
        "windows-1250",
        ImportSource.TAX,
        "csv",
        lambda t: tax_csv([tax_file(t, f"{POLISH} {t}")]).decode().encode("cp1250"),
        HTTPStatus.BAD_REQUEST,
        ImportErrorPayload.PARSE_FAILED,
    ),
    (
        "nul-byte",
        ImportSource.MASTER,
        "csv",
        lambda t: master_csv([master_file(t, city="Kra\x00ków")]),
        HTTPStatus.BAD_REQUEST,
        ImportErrorPayload.INVALID_STRUCTURE,
    ),
    (
        "nul-byte",
        ImportSource.TAX,
        "csv",
        lambda t: tax_csv([tax_file(t, f"Nul\x00 {t}")]),
        HTTPStatus.BAD_REQUEST,
        ImportErrorPayload.INVALID_STRUCTURE,
    ),
    (
        "cell-over-the-limit",
        ImportSource.MASTER,
        "csv",
        lambda t: master_csv([master_file(t, street=t + "x" * CELL_LIMIT)]),
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        ImportErrorPayload.RESOURCE_LIMIT,
    ),
    (
        "cell-over-the-limit",
        ImportSource.TAX,
        "csv",
        lambda t: tax_csv([tax_file(t, t + "x" * CELL_LIMIT)]),
        HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
        ImportErrorPayload.RESOURCE_LIMIT,
    ),
    (
        "extra-column",
        ImportSource.MASTER,
        "csv",
        lambda t: master_csv([master_file(t)]).replace(b"\n", b";nadmiar\n"),
        HTTPStatus.BAD_REQUEST,
        ImportErrorPayload.INVALID_STRUCTURE,
    ),
    (
        "extra-column",
        ImportSource.TAX,
        "csv",
        lambda t: tax_csv([tax_file(t)]).rstrip(b"\n") + b";nadmiar\n",
        HTTPStatus.BAD_REQUEST,
        ImportErrorPayload.INVALID_STRUCTURE,
    ),
    (
        "csv-named-xlsx",
        ImportSource.MASTER,
        "xlsx",
        lambda t: master_csv([master_file(t)]),
        HTTPStatus.BAD_REQUEST,
        ImportErrorPayload.PARSE_FAILED,
    ),
    (
        "xlsx-named-csv",
        ImportSource.TAX,
        "csv",
        lambda t: tax_xlsx([tax_file(t).cells()]),
        HTTPStatus.BAD_REQUEST,
        ImportErrorPayload.PARSE_FAILED,
    ),
]


@allure.feature("Negative import cases")
class TestSourceNegativeCases(BaseApiTest):
    @pytest.mark.parametrize(
        ("source", "extension", "build", "status", "payload"),
        [pytest.param(*case[1:], id=f"{case[1]}-{case[0]}") for case in CASES],
    )
    def test_a_broken_master_or_tax_file_is_refused(
        self,
        api: AlmaSpeiApi,
        db: DbQueries,
        tag: str,
        source: str,
        extension: str,
        build: Callable[[str], bytes],
        status: HTTPStatus,
        payload: dict[str, str],
    ):
        # 1. Note the donor and payment tables
        # 2. Upload the broken file as its source
        # 3. Verification: refused as a whole with the Polish message, never a server error,
        #    and the donor and payment tables are unchanged
        before = db_steps.read_canonical_counts(db)
        separator = None if extension == "xlsx" else CsvSeparator.SEMICOLON
        response = imports_steps.upload(
            api, f"{tag}.{extension}", build(tag), separator=separator, source=source
        )
        with soft_assertions():
            assert_error_includes(response, status, payload)
            assert_that(db_steps.read_canonical_counts(db)).described_as(
                "a refused file should not touch the donor and payment tables"
            ).is_equal_to(before)

    def test_a_master_workbook_with_merged_cells_is_refused(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a master XLSX with merged cells
        # 2. Verification: 400 unsupported format
        content = master_xlsx([master_file(tag).cells()], sheet_extra=MERGED_CELLS)
        response = imports_steps.upload(
            api, f"{tag}.xlsx", content, separator=None, source=ImportSource.MASTER
        )
        assert_error_includes(
            response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.UNSUPPORTED_FORMAT
        )

    @pytest.mark.xfail(strict=True, reason=TRAILING_CR_BUG)
    @pytest.mark.parametrize("source", [ImportSource.MASTER, ImportSource.TAX])
    def test_a_file_ending_with_a_lone_cr_has_only_its_rows(
        self, api: AlmaSpeiApi, tag: str, source: str
    ):
        # 1. Upload a master or tax CSV whose lines end with CR only
        # 2. Verification: exactly one staged row, as in the file
        if source == ImportSource.MASTER:
            content = master_csv([master_file(tag)])
        else:
            content = tax_csv([tax_file(tag)])
        body = imports_steps.upload_staged(
            api, f"{tag}.csv", content.replace(b"\n", b"\r"), source=source
        )
        assert_that(len(body["rows"])).described_as(
            "a lone CR should end a line, not add a row"
        ).is_equal_to(1)
