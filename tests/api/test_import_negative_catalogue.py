"""API tests for the catalogue of damaged and unusual bank files.

Each case is one file from ``docs/negative-import-cases.md`` with its expected
outcome: either the batch is staged (201) and every non-empty line is reported,
valid or with its Polish reasons, or the whole file is refused with a Polish
message (4xx). No case may end in a server error, and the donor and payment
tables never change before an import is approved.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error_includes
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    IMPORT_FILE_LIMIT_BYTES,
    IMPORT_PAGE_MAX_LIMIT,
    CsvSeparator,
    ImportErrorPayload,
    RowErrorCode,
)
from alma_spei_tests.data.corrupt import (
    csv_lines,
    inline_cell,
    number_cell,
    text_row,
    valid_line,
    xlsx_row,
    xlsx_workbook,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, imports_steps
from alma_spei_tests.testbase import BaseApiTest

DATE = RowErrorCode.INVALID_DATE
SENDER = RowErrorCode.MISSING_SENDER
AMOUNT = RowErrorCode.INVALID_AMOUNT
VALID: tuple[str, ...] = ()

#: The longest cell the parser accepts (characters).
CELL_LIMIT = 4096
#: The most rows a file may have.
ROW_LIMIT = 50000

#: A line break, to count the lines of a large file.
#: A line break, to count the lines of a large file.
NEWLINE = b"\n"
#: Excel's serial-date epochs.
EPOCH_1900 = dt.date(1899, 12, 30)
EPOCH_1904 = dt.date(1904, 1, 1)
SOME_DAY = dt.date(2026, 1, 15)


@dataclass(frozen=True)
class Staged:
    """201: the rows (number, validation codes) and the skipped blank lines.

    ``senders`` - when given - are the stored senders, to show a value is kept
    as written; ``count_only`` checks just the batch totals (for large files).
    """

    rows: tuple[tuple[int, tuple[str, ...]], ...]
    skipped: int = 0
    senders: tuple[str, ...] | None = None
    dates: tuple[str, ...] | None = None
    amounts: tuple[str, ...] | None = None


@dataclass(frozen=True)
class StagedCount:
    """201 for a large file: every line staged valid, counted on the batch."""


@dataclass(frozen=True)
class Refused:
    """The whole file is refused with this status and payload."""

    status: HTTPStatus
    payload: dict[str, str]


Outcome = Staged | StagedCount | Refused


@dataclass(frozen=True)
class Case:
    id: str
    build: Callable[[str], bytes]
    expected: Outcome
    extension: str = "csv"
    separator: CsvSeparator | None = CsvSeparator.SEMICOLON
    #: Set for a case whose expected outcome the app does not reach yet (a filed bug).
    known_bug: str | None = None


def lines(*make: Callable[[str], str], **options: Any) -> Callable[[str], bytes]:
    """A CSV builder from per-tag line builders."""
    return lambda tag: csv_lines([line(tag) for line in make], **options)


def ok(number: int, **kwargs: Any) -> Callable[[str], str]:
    return lambda tag: valid_line(tag, number, **kwargs)


def raw(template: str) -> Callable[[str], str]:
    """A literal line; ``{tag}`` is replaced by the test's tag."""
    return lambda tag: template.replace("{tag}", tag)


def staged(*rows: tuple[int, tuple[str, ...]], **kwargs: Any) -> Staged:
    return Staged(tuple(rows), **kwargs)


def refused(status: HTTPStatus, payload: dict[str, str]) -> Refused:
    return Refused(status, payload)


BAD_FILE = refused(HTTPStatus.BAD_REQUEST, ImportErrorPayload.PARSE_FAILED)
BAD_STRUCTURE = refused(HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE)
UNSUPPORTED = refused(HTTPStatus.BAD_REQUEST, ImportErrorPayload.UNSUPPORTED_FORMAT)
TOO_LARGE = refused(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, ImportErrorPayload.RESOURCE_LIMIT)
POLISH = "Zażółć Gęślą {tag}"


def with_amount(amount: str) -> Callable[[str], bytes]:
    return lines(ok(1, amount=amount))


def with_date(date: str) -> Callable[[str], bytes]:
    return lines(raw(date + ";Jan Testowy {tag};Darowizna {tag};10,00"))


def with_sender(sender: str) -> Callable[[str], bytes]:
    return lambda tag: csv_lines([valid_line(tag, 1, sender=sender.replace("{tag}", tag))])


def kept(sender: str) -> Staged:
    """One valid row whose sender is stored exactly as written (``{tag}`` filled in later)."""
    return staged((1, VALID), senders=(sender,))


def near_the_size_limit(tag: str) -> bytes:
    """Valid rows with long descriptions, a little under the 5 MiB file limit."""
    description = "x" * (CELL_LIMIT - 64)
    line = f"2026-01-15;Jan Testowy {tag};{description};10,00\n".encode()
    return line * ((IMPORT_FILE_LIMIT_BYTES - 1024) // len(line))


def over_the_row_limit(tag: str) -> bytes:
    return f"2026-01-15;J {tag};d;1\n".encode() * (ROW_LIMIT + 1)


def xlsx(*rows: Callable[[str], str], **options: Any) -> Callable[[str], bytes]:
    return lambda tag: xlsx_workbook([row(tag) for row in rows], **options)


def serial_row(serial: int, *, date_style: bool = True) -> Callable[[str], str]:
    return lambda tag: xlsx_row(
        1,
        [
            number_cell("A1", str(serial), date_style=date_style),
            inline_cell("B1", f"Jan Testowy {tag}"),
            inline_cell("C1", f"Darowizna {tag}"),
            inline_cell("D1", "10,00"),
        ],
    )


#: A file whose last line ends with a lone CR gets a phantom invalid row (filed bug).
TRAILING_CR_BUG = (
    "a trailing CR is read back as U+FFFF and staged as an extra invalid row"
    " (clojure.data.csv unreads the end of file); filed as a bug"
)

CATALOGUE = [
    # --- encoding ----------------------------------------------------------------
    Case("utf8-with-bom", lines(ok(1), ok(2), bom=True), staged((1, VALID), (2, VALID))),
    Case("utf16", lines(ok(1), encoding="utf-16"), BAD_FILE),
    Case(
        "windows-1250-polish",
        lambda t: csv_lines(
            [valid_line(t, 1, sender=POLISH.replace("{tag}", t))], encoding="cp1250"
        ),
        BAD_FILE,
    ),  # noqa: E501
    Case(
        "iso-8859-2-polish",
        lambda t: csv_lines(
            [valid_line(t, 1, sender=POLISH.replace("{tag}", t))], encoding="iso-8859-2"
        ),
        BAD_FILE,
    ),  # noqa: E501
    Case("windows-1250-ascii-only", lines(ok(1), encoding="cp1250"), staged((1, VALID))),
    Case(
        "invalid-utf8-sequence",
        lambda t: csv_lines([valid_line(t, 1)]).replace(b"Jan", b"J\xc3\x28n"),
        BAD_FILE,
    ),
    Case(
        "mixed-encodings",
        lambda t: (
            csv_lines([valid_line(t, 1, sender=POLISH.replace("{tag}", t))])
            + csv_lines([valid_line(t, 2, sender=POLISH.replace("{tag}", t))], encoding="cp1250")
        ),
        BAD_FILE,
    ),
    # --- structure ---------------------------------------------------------------------
    Case(
        "three-columns",
        lines(raw("2026-01-15;Jan Testowy {tag};Darowizna")),
        staged((1, (AMOUNT,))),
    ),  # noqa: E501
    Case(
        "five-columns",
        lines(raw("2026-01-15;Jan Testowy {tag};Darowizna;10,00;nadmiar")),
        BAD_STRUCTURE,
    ),  # noqa: E501
    Case(
        "ragged-rows",
        lines(ok(1), raw("2026-01-02;Jan Testowy {tag};Darowizna")),
        staged((1, VALID), (2, (AMOUNT,))),
    ),
    Case(
        "header-row",
        lines(raw("Data;Nadawca;Opis;Kwota"), ok(2), ok(3)),
        staged((1, (DATE, AMOUNT)), (2, VALID), (3, VALID)),
    ),
    Case(
        "blank-and-whitespace-lines",
        lines(ok(1), raw(""), raw("   "), ok(4)),
        staged((1, VALID), (4, VALID), skipped=2),
    ),
    Case(
        "no-trailing-newline",
        lines(ok(1), ok(2), trailing_newline=False),
        staged((1, VALID), (2, VALID)),
    ),  # noqa: E501
    Case("crlf-line-endings", lines(ok(1), ok(2), newline="\r\n"), staged((1, VALID), (2, VALID))),  # noqa: E501
    Case(
        "cr-line-endings",
        lines(ok(1), ok(2), newline="\r"),
        staged((1, VALID), (2, VALID)),
        known_bug=TRAILING_CR_BUG,
    ),
    Case(
        "mixed-line-endings",
        lambda t: f"{valid_line(t, 1)}\r\n{valid_line(t, 2)}\n{valid_line(t, 3)}\r".encode(),
        staged((1, VALID), (2, VALID), (3, VALID)),
        known_bug=TRAILING_CR_BUG,
    ),
    Case(
        "crlf-without-final-newline",
        lambda t: f"{valid_line(t, 1)}\r\n{valid_line(t, 2)}".encode(),
        staged((1, VALID), (2, VALID)),
    ),
    # --- separators ------------------------------------------------------------------
    Case(
        "commas-read-with-semicolon",
        lines(raw("2026-01-15,Jan Testowy {tag},Darowizna,10.00")),
        staged((1, (DATE, SENDER, AMOUNT))),
    ),
    Case(
        "mixed-separators",
        lines(ok(1), raw("2026-01-02,Jan Testowy {tag},Darowizna,10.00")),
        staged((1, VALID), (2, (DATE, SENDER, AMOUNT))),
    ),
    Case(
        "tab-separated",
        lines(raw("2026-01-15\tJan Testowy {tag}\tDarowizna\t10,00")),
        staged((1, (DATE, SENDER, AMOUNT))),
    ),
    Case("separator-inside-unquoted-field", with_sender("Kowalski; Jan {tag}"), BAD_STRUCTURE),
    # --- quotes ------------------------------------------------------------------------
    Case("quoted-separator", with_sender('"Kowalski; Jan {tag}"'), kept("Kowalski; Jan {tag}")),
    Case(
        "doubled-quotes", with_sender('"Fundacja ""Dobro"" {tag}"'), kept('Fundacja "Dobro" {tag}')
    ),  # noqa: E501
    Case(
        "newline-in-quoted-field",
        lambda t: csv_lines([valid_line(t, 1, sender=f'"Jan\nTestowy {t}"'), valid_line(t, 2)]),
        staged((1, VALID), (2, VALID), senders=("Jan\nTestowy {tag}", "Jan Testowy {tag}")),
    ),
    Case(
        "quote-inside-unquoted-field", with_sender('Jan "Junior" {tag}'), kept('Jan "Junior" {tag}')
    ),  # noqa: E501
    Case(
        "unclosed-quote",
        lines(ok(1), raw('2026-01-02;"Jan Testowy {tag};Darowizna;10,00'), ok(3)),
        BAD_FILE,
    ),
    # --- dates ------------------------------------------------------------------------
    Case("impossible-iso-date", with_date("2026-02-30"), staged((1, (DATE,)))),
    Case("impossible-polish-date", with_date("30.02.2026"), staged((1, (DATE,)))),
    Case("us-date", with_date("01/15/2026"), staged((1, (DATE,)))),
    Case("two-digit-year", with_date("15.01.26"), staged((1, (DATE,)))),
    Case("future-date", with_date("2099-12-31"), staged((1, VALID), dates=("2099-12-31",))),
    Case("very-old-date", with_date("1900-01-01"), staged((1, VALID), dates=("1900-01-01",))),
    Case("date-with-spaces", with_date(" 2026-01-15 "), staged((1, VALID), dates=("2026-01-15",))),
    # --- amounts ------------------------------------------------------------------------
    Case("space-thousands", with_amount("1 000,00"), staged((1, (AMOUNT,)))),
    Case("dot-thousands-and-comma-decimals", with_amount("1.000,00"), staged((1, (AMOUNT,)))),
    Case("currency-symbol", with_amount("100 zł"), staged((1, (AMOUNT,)))),
    Case("currency-code", with_amount("PLN 100"), staged((1, (AMOUNT,)))),
    Case("scientific-notation", with_amount("1e3"), staged((1, (AMOUNT,)))),
    Case("zero", with_amount("0,00"), staged((1, (AMOUNT,)))),
    Case("five-decimals", with_amount("10,12345"), staged((1, (AMOUNT,)))),
    Case("seventeen-digits", with_amount("12345678901234567,00"), staged((1, (AMOUNT,)))),
    Case("empty-amount", with_amount(""), staged((1, (AMOUNT,)))),
    Case("negative-amount", with_amount("-50,00"), staged((1, VALID))),
    Case("plus-sign", with_amount("+10,00"), staged((1, VALID))),
    # A dot is a decimal separator for the parser, so "1.000" is one zloty. Whether
    # a Polish thousands dot should be refused instead is open (reported to dev).
    Case(
        "dot-thousands-without-decimals",
        with_amount("1.000"),
        staged((1, VALID), amounts=("1.000",)),
    ),
    # --- fields -------------------------------------------------------------------------
    Case("empty-sender", with_sender(""), staged((1, (SENDER,)))),
    Case(
        "sender-at-the-cell-limit",
        lambda t: csv_lines([valid_line(t, 1, sender=t + "x" * (CELL_LIMIT - len(t)))]),
        staged((1, VALID)),
    ),  # noqa: E501
    Case(
        "sender-over-the-cell-limit",
        lambda t: csv_lines([valid_line(t, 1, sender=t + "x" * (CELL_LIMIT + 1 - len(t)))]),
        TOO_LARGE,
    ),  # noqa: E501
    Case("nul-byte", with_sender("Jan\x00 {tag}"), BAD_STRUCTURE),
    Case("control-character", with_sender("Jan\x07 {tag}"), kept("Jan\x07 {tag}")),
    Case("emoji", with_sender("Jan 😀 {tag}"), kept("Jan 😀 {tag}")),
    Case("polish-letters", with_sender(POLISH), kept(POLISH)),
    Case("right-to-left-override", with_sender("Jan ‮{tag}"), kept("Jan ‮{tag}")),
    # --- formula injection: kept as plain text ------------------------------------------
    Case("formula-equals", with_sender("=1+1 {tag}"), kept("=1+1 {tag}")),
    Case("formula-plus", with_sender("+48 600 100 200 {tag}"), kept("+48 600 100 200 {tag}")),
    Case("formula-minus", with_sender("-2+3 {tag}"), kept("-2+3 {tag}")),
    Case("formula-at", with_sender("@SUM(A1) {tag}"), kept("@SUM(A1) {tag}")),
    # --- whole files ----------------------------------------------------------------------
    Case("bom-only", lambda t: b"\xef\xbb\xbf", BAD_STRUCTURE),
    Case(
        "truncated-mid-row",
        lambda t: csv_lines([valid_line(t, 1)]) + f"2026-01-02;Jan Tes{t}".encode(),
        staged((1, VALID), (2, (AMOUNT,))),
    ),
    Case("binary-junk", lambda t: b"\xff\xfe\x80" * 32 + t.encode(), BAD_FILE),
    Case("xlsx-named-csv", xlsx(lambda t: text_row(1, t)), BAD_FILE),
    Case("csv-named-xlsx", lines(ok(1)), BAD_FILE, extension="xlsx", separator=None),
    Case("just-under-the-size-limit", near_the_size_limit, StagedCount()),  # noqa: E501
    Case("over-the-row-limit", over_the_row_limit, TOO_LARGE),
    # --- XLSX ----------------------------------------------------------------------------
    Case(
        "xlsx-truncated-archive",
        lambda t: xlsx_workbook([text_row(1, t)])[:400],
        BAD_FILE,
        extension="xlsx",
        separator=None,
    ),
    Case("xlsx-two-sheets", xlsx(lambda t: text_row(1, t), sheets=2), BAD_STRUCTURE, "xlsx", None),
    Case(
        "xlsx-formula",
        xlsx(
            lambda t: xlsx_row(
                1,
                [
                    inline_cell("A1", "2026-01-15"),
                    inline_cell("B1", f"Jan Testowy {t}"),
                    inline_cell("C1", "Darowizna"),
                    "<c r='D1'><f>5+5</f><v>10</v></c>",
                ],
            )
        ),
        UNSUPPORTED,
        "xlsx",
        None,
    ),
    Case(
        "xlsx-merged-cells",
        xlsx(
            lambda t: text_row(1, t),
            sheet_extra="<mergeCells count='1'><mergeCell ref='B1:C1'/></mergeCells>",
        ),
        UNSUPPORTED,
        "xlsx",
        None,
    ),
    Case(
        "xlsx-fifth-column",
        xlsx(lambda t: text_row(1, t).replace("</row>", inline_cell("E1", "nadmiar") + "</row>")),
        BAD_STRUCTURE,
        "xlsx",
        None,
    ),
    Case(
        "xlsx-date-as-text",
        xlsx(lambda t: text_row(1, t)),
        staged((1, VALID), dates=("2026-01-15",)),
        "xlsx",
        None,
    ),  # noqa: E501
    Case(
        "xlsx-date-as-serial",
        xlsx(serial_row((SOME_DAY - EPOCH_1900).days)),
        staged((1, VALID), dates=(SOME_DAY.isoformat(),)),
        "xlsx",
        None,
    ),
    Case(
        "xlsx-1904-date-system",
        xlsx(serial_row((SOME_DAY - EPOCH_1904).days), date1904=True),
        staged((1, VALID), dates=(SOME_DAY.isoformat(),)),
        "xlsx",
        None,
    ),
    Case(
        "xlsx-serial-without-date-format",
        xlsx(serial_row((SOME_DAY - EPOCH_1900).days, date_style=False)),
        staged((1, (DATE,))),
        "xlsx",
        None,
    ),
    Case(
        "xlsx-hidden-row",
        xlsx(lambda t: text_row(1, t), lambda t: text_row(2, t, hidden=True)),
        staged((1, VALID), (2, VALID)),
        "xlsx",
        None,
    ),
]


#: The catalogue as test parameters; a known bug is a strict expected failure.
CASES = [
    pytest.param(
        case,
        id=case.id,
        marks=[pytest.mark.xfail(strict=True, reason=case.known_bug)] if case.known_bug else [],
    )
    for case in CATALOGUE
]


@allure.feature("Negative import cases")
class TestNegativeImportCatalogue(BaseApiTest):
    @pytest.mark.parametrize("case", CASES)
    def test_a_damaged_file_gets_its_catalogued_outcome(
        self, api: AlmaSpeiApi, db: DbQueries, case: Case, tag: str
    ):
        # 1. Note the donor and payment tables
        # 2. Upload the catalogue file
        # 3. Verification: no server error; staged with every row reported as catalogued, or
        #    refused with the Polish message; the donor and payment tables are unchanged
        before = db_steps.read_canonical_counts(db)
        content = case.build(tag)
        response = imports_steps.upload(
            api, f"{tag}.{case.extension}", content, separator=case.separator
        )
        with soft_assertions():
            assert_that(response.status_code).described_as(
                "a damaged file should never cause a server error"
            ).is_less_than(HTTPStatus.INTERNAL_SERVER_ERROR)
            assert_outcome(api, response, case.expected, tag, content)
            assert_that(db_steps.read_canonical_counts(db)).described_as(
                "uploading should not touch the donor and payment tables"
            ).is_equal_to(before)


# --- file-local helpers -------------------------------------------------------
def assert_outcome(api: AlmaSpeiApi, response: Any, expected: Outcome, tag: str, content: bytes):
    if isinstance(expected, Refused):
        assert_error_includes(response, expected.status, expected.payload)
        return
    assert_that(response.status_code).described_as(
        f"the file should be staged (body: {response.text[:300]})"
    ).is_equal_to(HTTPStatus.CREATED)
    if response.status_code != HTTPStatus.CREATED:
        return
    body = response.json()
    if isinstance(expected, StagedCount):
        batch = body["batch"]
        assert_that((batch["total-rows"], batch["valid-rows"])).described_as(
            "every row of the large file should be staged valid"
        ).is_equal_to((content.count(NEWLINE), content.count(NEWLINE)))
        return
    rows = imports_steps.read_rows(api, body["batch"]["id"], limit=IMPORT_PAGE_MAX_LIMIT).json()[
        "rows"
    ]
    assert_that(
        [(r["row-number"], tuple(e["code"] for e in r["errors"])) for r in rows]
    ).described_as(
        "every non-empty line should be reported, valid or with its reasons"
    ).is_equal_to(list(expected.rows))
    assert_that(body["skipped-empty-rows"]).described_as(
        "blank lines should be skipped and counted"
    ).is_equal_to(expected.skipped)
    if expected.senders is not None:
        assert_that([r["payload"]["sender"] for r in rows]).described_as(
            "the sender should be stored exactly as written, as plain text"
        ).is_equal_to([sender.replace("{tag}", tag) for sender in expected.senders])
    if expected.amounts is not None:
        assert_that([r["payload"]["amount"] for r in rows]).described_as(
            "the amount should be read by the confirmed dot-or-comma decimal rule"
        ).is_equal_to(list(expected.amounts))
    if expected.dates is not None:
        assert_that([r["payload"]["date"] for r in rows]).described_as(
            "the date should be read as written"
        ).is_equal_to(list(expected.dates))
