"""Synthetic bank statements for the import upload (task 35).

The bank adapter reads four positional columns - ``date;sender;description;
amount`` - with no header. Dates are ``YYYY-MM-DD`` or ``DD.MM.YYYY`` (XLSX may
also use a date-styled serial number); amounts use a dot or comma decimal.

The backend refuses a byte-identical file twice (409 duplicate-file), so every
statement embeds a unique tag in its descriptions. Everything here is invented.
"""

import datetime as dt
import hashlib
import io
import zipfile
from dataclasses import dataclass
from xml.sax.saxutils import escape

from faker import Faker

from alma_spei_tests.constants import CsvSeparator
from alma_spei_tests.data.factories import TAG_PREFIX, seeded_faker

#: The XLSX date-serial epoch (1900 system, with Excel's fictitious 1900-02-29).
_XLSX_EPOCH = dt.date(1899, 12, 30)


@dataclass(frozen=True)
class BankRow:
    """One statement line exactly as written to the file (raw source text)."""

    date: str | dt.date
    sender: str
    description: str
    amount: str

    @property
    def date_text(self) -> str:
        """The date cell as written to the file (ISO for ``date`` values)."""
        return self.date.isoformat() if isinstance(self.date, dt.date) else self.date

    def cells(self) -> list[str]:
        return [self.date_text, self.sender, self.description, self.amount]


@dataclass(frozen=True)
class BankStatement:
    rows: list[BankRow]
    #: Blank lines appended after the rows (the parser skips and counts them).
    trailing_blank_lines: int = 0
    separator: CsvSeparator = CsvSeparator.SEMICOLON

    # --- CSV ------------------------------------------------------------------
    def to_csv(self) -> bytes:
        lines = [
            self.separator.join(_csv_cell(cell, self.separator) for cell in row.cells())
            for row in self.rows
        ]
        lines += [""] * self.trailing_blank_lines
        return ("\n".join(lines) + "\n").encode("utf-8")

    # --- XLSX -----------------------------------------------------------------
    def to_xlsx(self, first_row: int = 1) -> bytes:
        """A minimal single-sheet workbook; dates given as ``date`` become serials."""
        sheet_rows = "".join(
            _xlsx_row(first_row + index, row) for index, row in enumerate(self.rows)
        )
        parts = dict(_XLSX_PARTS)
        parts["xl/worksheets/sheet1.xml"] = (
            f"<worksheet xmlns='{_MAIN_NS}'><sheetData>{sheet_rows}</sheetData></worksheet>"
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, text in parts.items():
                archive.writestr(name, text)
        return buffer.getvalue()


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def new_bank_statement(
    tag: str, *, rows: int = 2, seed: int | None = None, fake: Faker | None = None
) -> BankStatement:
    """``rows`` valid synthetic lines whose descriptions carry ``tag``."""
    fake = fake or seeded_faker(seed)
    return BankStatement(
        rows=[
            BankRow(
                date=dt.date(2026, 1, 2) + dt.timedelta(days=index),
                sender=fake.name(),
                description=f"Darowizna {tag} #{index + 1}",
                amount=f"{fake.random_int(1, 999)},{fake.random_int(0, 99):02d}",
            )
            for index in range(rows)
        ]
    )


def blank_only_csv(tag: str) -> bytes:
    """Only whitespace lines - no rows - unique per tag (one line per hex digit)."""
    digits = tag.removeprefix(TAG_PREFIX)
    return "\n".join(" " * (int(digit, 16) + 1) for digit in digits).encode() + b"\n"


# --- internals ----------------------------------------------------------------
def _csv_cell(value: str, separator: str) -> str:
    if any(ch in value for ch in (separator, '"', "\n", "\r")):
        return '"' + value.replace('"', '""') + '"'
    return value


def _xlsx_row(number: int, row: BankRow) -> str:
    cells = []
    values = (row.date, row.sender, row.description, row.amount)
    for column, value in zip("ABCD", values, strict=True):
        ref = f"{column}{number}"
        if isinstance(value, dt.date):  # date-styled serial (style 1 = numFmt 14)
            cells.append(f"<c r='{ref}' s='1'><v>{(value - _XLSX_EPOCH).days}</v></c>")
        elif column == "D":  # numeric amount
            cells.append(f"<c r='{ref}'><v>{escape(value.replace(',', '.'))}</v></c>")
        elif value:
            cells.append(f"<c r='{ref}' t='inlineStr'><is><t>{escape(value)}</t></is></c>")
    return f"<row r='{number}'>{''.join(cells)}</row>"


_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_PKG_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
_OFFICE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml"

# Mirrors the app's own synthetic fixture (dev/alma_spei/dev/bank_fixtures.clj).
_XLSX_PARTS = {
    "[Content_Types].xml": (
        "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
        "<Default Extension='rels' "
        "ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
        "<Default Extension='xml' ContentType='application/xml'/>"
        f"<Override PartName='/xl/workbook.xml' ContentType='{_CT}.sheet.main+xml'/>"
        f"<Override PartName='/xl/worksheets/sheet1.xml' ContentType='{_CT}.worksheet+xml'/>"
        f"<Override PartName='/xl/styles.xml' ContentType='{_CT}.styles+xml'/>"
        "</Types>"
    ),
    "_rels/.rels": (
        f"<Relationships xmlns='{_PKG_RELS}'><Relationship Id='rId1' "
        f"Type='{_OFFICE_REL}/officeDocument' Target='xl/workbook.xml'/></Relationships>"
    ),
    "xl/workbook.xml": (
        f"<workbook xmlns='{_MAIN_NS}' xmlns:r='{_OFFICE_REL}'><workbookPr date1904='0'/>"
        "<sheets><sheet name='Synthetic' sheetId='1' r:id='rId1'/></sheets></workbook>"
    ),
    "xl/_rels/workbook.xml.rels": (
        f"<Relationships xmlns='{_PKG_RELS}'>"
        f"<Relationship Id='rId1' Type='{_OFFICE_REL}/worksheet' Target='worksheets/sheet1.xml'/>"
        f"<Relationship Id='rId2' Type='{_OFFICE_REL}/styles' Target='styles.xml'/>"
        "</Relationships>"
    ),
    "xl/styles.xml": (
        f"<styleSheet xmlns='{_MAIN_NS}'><cellXfs count='2'>"
        "<xf numFmtId='0'/><xf numFmtId='14'/></cellXfs></styleSheet>"
    ),
}
