"""Broken and unusual bank files for the negative import tests.

Two kinds of input:

* **Catalogue helpers** (``csv_lines``, ``xlsx_workbook``) build one specific
  file per catalogue case: an encoding, a line ending, a quoting problem, an
  XLSX feature.
* **Generated corruptions** (``generated_corruptions``) start from a valid
  statement and apply random damage - nasty field values, missing or extra
  columns, blank lines, other line endings, truncation, flipped bytes, other
  encodings - from a fixed seed, so a failing example can be replayed.

Every file carries the test's tag, because the backend refuses a byte-identical
file twice. Everything here is invented.
"""

import io
import random
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from alma_spei_tests.constants import CsvSeparator
from alma_spei_tests.data.bank import _MAIN_NS, _OFFICE_REL, _XLSX_PARTS

#: The byte-order mark of UTF-8.
UTF8_BOM = b"\xef\xbb\xbf"


def valid_line(tag: str, number: int, *, sender: str | None = None, amount: str = "10,00") -> str:
    """One well-formed ``date;sender;description;amount`` line."""
    who = sender if sender is not None else f"Jan Testowy {tag}"
    return f"2026-01-{number:02d};{who};Darowizna {tag} #{number};{amount}"


def csv_lines(
    lines: Sequence[str],
    *,
    encoding: str = "utf-8",
    bom: bool = False,
    newline: str = "\n",
    trailing_newline: bool = True,
) -> bytes:
    """The lines joined with ``newline`` and encoded; optionally with a UTF-8 BOM."""
    text = newline.join(lines) + (newline if trailing_newline else "")
    return (UTF8_BOM if bom else b"") + text.encode(encoding)


# --- XLSX -----------------------------------------------------------------------
def inline_cell(ref: str, value: str) -> str:
    return f"<c r='{ref}' t='inlineStr'><is><t>{escape(value)}</t></is></c>"


def number_cell(ref: str, value: str, *, date_style: bool = False) -> str:
    style = " s='1'" if date_style else ""
    return f"<c r='{ref}'{style}><v>{value}</v></c>"


def xlsx_row(number: int, cells: Sequence[str], *, hidden: bool = False) -> str:
    flag = " hidden='1'" if hidden else ""
    return f"<row r='{number}'{flag}>{''.join(cells)}</row>"


def text_row(number: int, tag: str, *, date: str = "2026-01-15", hidden: bool = False) -> str:
    """A valid statement row with every cell as text (the amount with a comma)."""
    return xlsx_row(
        number,
        [
            inline_cell(f"A{number}", date),
            inline_cell(f"B{number}", f"Jan Testowy {tag}"),
            inline_cell(f"C{number}", f"Darowizna {tag} #{number}"),
            inline_cell(f"D{number}", "10,00"),
        ],
        hidden=hidden,
    )


def xlsx_workbook(
    rows: Sequence[str],
    *,
    date1904: bool = False,
    sheets: int = 1,
    sheet_extra: str = "",
    sheet_prefix: str = "",
) -> bytes:
    """A minimal workbook whose first sheet holds ``rows`` (``<row>`` elements).

    ``sheets`` > 1 adds more (empty) sheets; ``sheet_extra`` is appended after
    ``sheetData`` (e.g. ``mergeCells``); ``sheet_prefix`` goes before the root
    element (e.g. a DOCTYPE).
    """
    parts = dict(_XLSX_PARTS)
    sheet_list = "".join(
        f"<sheet name='Arkusz{n}' sheetId='{n}' r:id='rId{n + 10}'/>" for n in range(1, sheets + 1)
    )
    parts["xl/workbook.xml"] = (
        f"<workbook xmlns='{_MAIN_NS}' xmlns:r='{_OFFICE_REL}'>"
        f"<workbookPr date1904='{1 if date1904 else 0}'/><sheets>{sheet_list}</sheets></workbook>"
    )
    relations = "".join(
        f"<Relationship Id='rId{n + 10}' Type='{_OFFICE_REL}/worksheet'"
        f" Target='worksheets/sheet{n}.xml'/>"
        for n in range(1, sheets + 1)
    )
    parts["xl/_rels/workbook.xml.rels"] = (
        "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
        f"{relations}<Relationship Id='rId2' Type='{_OFFICE_REL}/styles' Target='styles.xml'/>"
        "</Relationships>"
    )
    overrides = "".join(
        f"<Override PartName='/xl/worksheets/sheet{n}.xml' ContentType="
        "'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml'/>"
        for n in range(2, sheets + 1)
    )
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(
        "</Types>", f"{overrides}</Types>"
    )
    parts["xl/worksheets/sheet1.xml"] = (
        f"{sheet_prefix}<worksheet xmlns='{_MAIN_NS}'><sheetData>{''.join(rows)}</sheetData>"
        f"{sheet_extra}</worksheet>"
    )
    for n in range(2, sheets + 1):
        parts[f"xl/worksheets/sheet{n}.xml"] = (
            f"<worksheet xmlns='{_MAIN_NS}'><sheetData/></worksheet>"
        )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, text in parts.items():
            archive.writestr(name, text)
    return buffer.getvalue()


# --- generated corruptions -----------------------------------------------------------
#: Field values that have broken parsers before: separators, quotes, control
#: characters, formulas, other scripts, emoji, numbers in other notations.
NASTY_VALUES = (
    "",
    " ",
    ";",
    ",",
    '"',
    '""',
    "\t",
    "=1+1",
    "+48 600",
    "-2+3",
    "@SUM(A1)",
    "1 000,00",
    "1.000,00",
    "1e3",
    "100 zł",
    "-0,00",
    "99999999999999999,99",
    "31.02.2026",
    "2026-13-01",
    "Zażółć gęślą jaźń",
    "😀",
    "‮",
    "\x07",
    "' OR '1'='1",
    "<script>",
)

#: Encodings a file from a bank or a spreadsheet may come in.
OTHER_ENCODINGS = ("cp1250", "iso-8859-2", "utf-16")


@dataclass
class GeneratedFile:
    """One generated file and what the generator knows about it."""

    label: str
    content: bytes
    #: Non-blank physical lines, when the damage keeps one record per line.
    record_lines: int | None
    damage: list[str] = field(default_factory=list)


def _cells(tag: str, number: int) -> list[str]:
    return valid_line(tag, number).split(";")


def generated_corruptions(seed: int, count: int, tag: str) -> list[GeneratedFile]:
    """``count`` damaged CSV statements from ``seed`` (same seed, same files)."""
    rng = random.Random(seed)
    return [_corrupt(rng, f"{tag}-{seed}-{index}") for index in range(count)]


def _corrupt(rng: random.Random, tag: str) -> GeneratedFile:
    rows = [_cells(tag, number) for number in range(1, rng.randint(1, 6) + 1)]
    damage: list[str] = []
    for _ in range(rng.randint(1, 3)):
        name, mutate = rng.choice(_ROW_MUTATIONS)
        damage.append(name)
        mutate(rng, rows)
    # Without quotes every physical line is one record, so the lines can be counted.
    line_level = not any('"' in cell for cells in rows for cell in cells)
    # The tag stays in its own last line, so every file is unique.
    lines = [";".join(cells) for cells in rows] + [valid_line(tag, 28)]
    newline = rng.choice(["\n", "\r\n", "\n"])
    text = newline.join(lines) + newline
    content = text.encode("utf-8")
    byte_damage = rng.random()
    if byte_damage < 0.15:
        content = content.decode("utf-8").encode(rng.choice(OTHER_ENCODINGS), errors="replace")
        damage.append("encoding")
        line_level = False
    elif byte_damage < 0.3:
        position = rng.randrange(len(content))
        content = content[:position] + bytes([rng.randrange(256)]) + content[position + 1 :]
        damage.append("flipped-byte")
        line_level = False
    elif byte_damage < 0.4:
        content = content[: rng.randrange(1, len(content))]
        damage.append("truncated")
        line_level = False
    record_lines = (
        sum(
            1
            for line in text.replace("\r\n", "\n").split("\n")
            if any(cell.strip() for cell in line.split(";"))
        )
        if line_level
        else None
    )
    return GeneratedFile("+".join(damage), content, record_lines, damage)


def _nasty_field(rng: random.Random, rows: list[list[str]]):
    row = rng.choice(rows)
    if row:
        row[rng.randrange(len(row))] = rng.choice(NASTY_VALUES).replace("\n", " ")


def _drop_column(rng: random.Random, rows: list[list[str]]):
    row = rng.choice(rows)
    if row:
        del row[rng.randrange(len(row))]


def _extra_column(rng: random.Random, rows: list[list[str]]):
    rng.choice(rows).append("nadmiarowa")


def _blank_line(rng: random.Random, rows: list[list[str]]):
    rows.insert(rng.randrange(len(rows) + 1), [rng.choice(["", " ", "   "])])


def _quote(rng: random.Random, rows: list[list[str]]):
    row = rng.choice(rows)
    if row:
        index = rng.randrange(len(row))
        row[index] = rng.choice(['"', '"' + row[index], row[index] + '"x', f'"{row[index]};"'])


def _embedded_newline(rng: random.Random, rows: list[list[str]]):
    row = rng.choice(rows)
    if len(row) > 1:
        row[1] = f'"{row[1]}\nciąg dalszy"'


_ROW_MUTATIONS: list[tuple[str, Callable[[random.Random, list[list[str]]], None]]] = [
    ("nasty-field", _nasty_field),
    ("nasty-field", _nasty_field),
    ("drop-column", _drop_column),
    ("extra-column", _extra_column),
    ("blank-line", _blank_line),
    ("quote", _quote),
    ("embedded-newline", _embedded_newline),
]

#: The separator of every generated file.
GENERATED_SEPARATOR = CsvSeparator.SEMICOLON
