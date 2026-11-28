"""Synthetic master donor workbooks and 1.5% tax lists (tasks 65-67).

The layouts the adapters read:

* **master** (the donor base, ``source=master``): a header at row 1 -
  A full name, B street, C postal code, D city, E province, F gender,
  G-K the years 2021-2025, L the 1.5% column, M-X twelve further observation
  columns, Y a summary (never kept) and Z, whose meaning is unknown (a filled Z
  flags the row). Data rows follow from row 2.
* **tax** (the 1.5% list, ``source=tax``): two title lines (skipped), a header at
  row 3 - A ordinal, B-D the taxpayer's first name, surname and address, E-G the
  spouse's, H the specific purpose, I the transferred amount. Data rows follow
  from row 4.

Every value is invented and every file carries the test's tag, because the
backend refuses a byte-identical file twice - also across sources.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from alma_spei_tests.data.corrupt import inline_cell, number_cell, xlsx_row, xlsx_workbook

#: Excel column letters A..Z.
COLUMNS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

#: The master header: profile fields, years, the 1.5% column, twelve observation
#: columns, the summary and the unknown last column.
MASTER_HEADER = (
    "Imię i nazwisko",
    "Ulica",
    "Kod pocztowy",
    "Miejscowość",
    "Województwo",
    "Płeć",
    "2021",
    "2022",
    "2023",
    "2024",
    "2025",
    "1,5% podatku",
    *(f"Obserwacja {n}" for n in range(13, 25)),
    "Suma",
    "Uwagi",
)
#: The years of columns G-K, and the first and last observation columns (1-based).
MASTER_YEARS = (2021, 2022, 2023, 2024, 2025)
FIRST_OBSERVATION_COLUMN = 7
LAST_OBSERVATION_COLUMN = 24

TAX_TITLE = ("Wykaz przekazań 1,5% podatku - dane syntetyczne", "Urząd skarbowy: fikcyjny")
TAX_HEADER = (
    "L.p.",
    "Imię podatnika",
    "Nazwisko podatnika",
    "Adres podatnika",
    "Imię małżonka",
    "Nazwisko małżonka",
    "Adres małżonka",
    "Cel szczegółowy",
    "Kwota przekazana",
)
#: The first data row of a tax list.
TAX_FIRST_DATA_ROW = 4


@dataclass(frozen=True)
class MasterRow:
    """One donor of the master workbook; ``observations`` fill G-X (18 cells)."""

    name: str
    street: str = "ul. Lipowa 1/4"
    postal_code: str = "30-001"
    city: str = "Kraków"
    province: str = "małopolskie"
    gender: str = "K"
    observations: tuple[str, ...] = ("10", "20", "", "30", "40", "15,50", *("",) * 12)
    summary: str = "115,50"
    extra: str = ""

    def cells(self) -> list[str]:
        observed = (list(self.observations) + [""] * 18)[:18]
        profile = [self.name, self.street, self.postal_code, self.city, self.province]
        return [*profile, self.gender, *observed, self.summary, self.extra]

    def expected_observations(self, source_type: str = "text") -> list[dict[str, object]]:
        """The observations the adapter keeps: every filled G-X cell, years on G-K."""
        kept = []
        for offset, value in enumerate((list(self.observations) + [""] * 18)[:18]):
            if not value.strip():
                continue
            column = FIRST_OBSERVATION_COLUMN + offset
            item: dict[str, object] = {"column": column, "value": value, "source-type": source_type}
            if offset < len(MASTER_YEARS):
                item["year"] = MASTER_YEARS[offset]
            kept.append(item)
        return kept


@dataclass(frozen=True)
class TaxSubject:
    first_name: str = ""
    surname: str = ""
    address: str = ""

    def cells(self) -> list[str]:
        return [self.first_name, self.surname, self.address]

    def payload(self) -> dict[str, str]:
        fields = {"first-name": self.first_name, "surname": self.surname, "address": self.address}
        return {key: value for key, value in fields.items() if value}


@dataclass(frozen=True)
class TaxRow:
    """One entry of the 1.5% list; an empty subject is an anonymous declaration."""

    ordinal: str
    taxpayer: TaxSubject = field(default_factory=TaxSubject)
    spouse: TaxSubject = field(default_factory=TaxSubject)
    purpose: str = ""
    amount: str = "12,50"

    def cells(self) -> list[str]:
        return [
            self.ordinal,
            *self.taxpayer.cells(),
            *self.spouse.cells(),
            self.purpose,
            self.amount,
        ]


# --- files ------------------------------------------------------------------------
def master_csv(rows: Sequence[MasterRow], *, header: Sequence[str] = MASTER_HEADER) -> bytes:
    lines = [list(header), *(row.cells() for row in rows)]
    return _csv(lines)


def tax_csv(
    rows: Sequence[TaxRow],
    *,
    header: Sequence[str] = TAX_HEADER,
    title: Sequence[str] = TAX_TITLE,
) -> bytes:
    lines = [[title[0]], [title[1]], list(header), *(row.cells() for row in rows)]
    return _csv(lines)


def master_xlsx(
    rows: Sequence[Sequence[str]],
    *,
    numbers: frozenset[int] = frozenset(),
    dates: frozenset[int] = frozenset(),
    formulas: dict[int, str] | None = None,
    header: Sequence[str] = MASTER_HEADER,
    sheet_extra: str = "",
) -> bytes:
    """A master workbook; ``numbers``/``dates`` are 0-based columns written as numbers
    (``dates`` with a date format) and ``formulas`` columns as formulas in the data rows;
    ``sheet_extra`` is appended to the sheet (e.g. merged cells)."""
    sheet = [_text_row(1, header)]
    sheet += [
        _typed_row(number, cells, numbers, dates, formulas or {})
        for number, cells in enumerate(rows, start=2)
    ]
    return xlsx_workbook(sheet, sheet_extra=sheet_extra)


def tax_xlsx(
    rows: Sequence[Sequence[str]],
    *,
    numbers: frozenset[int] = frozenset(),
    header: Sequence[str] = TAX_HEADER,
) -> bytes:
    sheet = [_text_row(1, TAX_TITLE[:1]), _text_row(2, TAX_TITLE[1:]), _text_row(3, header)]
    sheet += [
        _typed_row(number, cells, numbers, frozenset(), {})
        for number, cells in enumerate(rows, start=TAX_FIRST_DATA_ROW)
    ]
    return xlsx_workbook(sheet)


# --- internals ----------------------------------------------------------------------
def _csv(lines: Sequence[Sequence[str]]) -> bytes:
    def cell(value: str) -> str:
        if any(ch in value for ch in ';"\n\r'):
            return '"' + value.replace('"', '""') + '"'
        return value

    return "".join(";".join(cell(v) for v in line) + "\n" for line in lines).encode()


def _text_row(number: int, values: Sequence[str]) -> str:
    cells = [inline_cell(f"{COLUMNS[i]}{number}", v) for i, v in enumerate(values) if v]
    return xlsx_row(number, cells)


def _typed_row(
    number: int,
    values: Sequence[str],
    numbers: frozenset[int],
    dates: frozenset[int],
    formulas: dict[int, str],
) -> str:
    cells = []
    for index, value in enumerate(values):
        ref = f"{COLUMNS[index]}{number}"
        if index in formulas:
            cells.append(f"<c r='{ref}'><f>{formulas[index]}</f><v>{value or 0}</v></c>")
        elif not value:
            continue
        elif index in numbers or index in dates:
            cells.append(number_cell(ref, value.replace(",", "."), date_style=index in dates))
        else:
            cells.append(inline_cell(ref, value))
    return xlsx_row(number, cells)
