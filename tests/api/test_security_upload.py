"""API security tests for the bank upload: file names, XLSX archives and XML.

The upload must not trust what the client sends:

* a file name is a bare name - no directories, drive letters or control
  characters - and only ``.csv`` and ``.xlsx`` are read;
* an XLSX is a zip of XML parts, so it is a vehicle for zip bombs, path
  traversal inside the archive, macros, external links and XML entity attacks
  (XXE, "billion laughs"). Each is refused before the content is processed, and
  nothing from the server's file system appears in an answer.

Size limits of the file itself are covered by ``test_bank_upload.py``.
"""

import io
import time
import zipfile
from http import HTTPStatus

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error_includes
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import ApiPath, ErrorCode, Header, ImportErrorPayload
from alma_spei_tests.data import BankStatement
from alma_spei_tests.steps import imports_steps
from alma_spei_tests.testbase import BaseApiTest

SHEET = "xl/worksheets/sheet1.xml"
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

#: Where an XXE would read from, and a line of that file that must never come back.
SECRET_FILE = "file:///etc/passwd"
SECRET_MARKER = "root:"

#: Generous time a refusal may take; a parser that expanded the entities would not finish.
REFUSAL_SECONDS = 10

#: The zip-entry limit of the XLSX reader.
ZIP_ENTRY_LIMIT = 128


def billion_laughs() -> str:
    """A DOCTYPE whose ten entity levels would expand to 10^9 "lol"s."""
    entities = ['<!ENTITY lol0 "lol">'] + [
        f'<!ENTITY lol{n} "{f"&lol{n - 1};" * 10}">' for n in range(1, 10)
    ]
    return f"<!DOCTYPE worksheet [{''.join(entities)}]>"


@allure.feature("Security: upload")
class TestFileNames(BaseApiTest):
    @pytest.mark.parametrize(
        "name",
        [
            pytest.param("../../etc/{tag}.csv", id="parent-directories"),
            pytest.param("..\\..\\windows\\{tag}.csv", id="windows-parent-directories"),
            pytest.param("/tmp/{tag}.csv", id="absolute-path"),
            pytest.param("C:\\Users\\{tag}.csv", id="drive-letter"),
            pytest.param("katalog/{tag}.csv", id="sub-directory"),
        ],
    )
    def test_a_file_name_with_a_path_is_refused(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str, name: str
    ):
        # 1. Upload a valid statement under a name with a path
        # 2. Verification: 400 import validation - only a bare file name is accepted
        response = imports_steps.upload(api, name.replace("{tag}", tag), bank_statement.to_csv())
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    @pytest.mark.parametrize("character", ["\t", "\x1b", "\x7f"], ids=["tab", "escape", "delete"])
    def test_a_file_name_with_a_control_character_is_refused(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str, character: str
    ):
        # 1. Upload a valid statement whose raw multipart file name holds a control character
        #    (built by hand: the HTTP client would escape it)
        # 2. Verification: 400, refused by the form reader or by the name validation
        response = upload_raw_name(api, f"{tag}{character}.csv".encode(), bank_statement.to_csv())
        with soft_assertions():
            assert_that(response.status_code).described_as(
                "a control character in a file name should be refused"
            ).is_equal_to(HTTPStatus.BAD_REQUEST)
            assert_that(response.json().get("code")).described_as(
                "the refusal should come from the form reader or the name validation"
            ).is_in(ErrorCode.INVALID_STRUCTURE, ErrorCode.VALIDATION)

    @pytest.mark.parametrize(
        "name", ["<b>{tag}.csv", "<img src=x onerror=alert(1)>{tag}.csv"], ids=["tag", "img"]
    )
    def test_a_file_name_with_markup_is_refused_or_kept_as_text(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str, name: str
    ):
        # 1. Upload a valid statement under a name holding HTML markup
        # 2. Verification: either refused as a whole (400, as the form reader on Windows
        #    does) or staged with the name stored exactly as written (as on Linux); the
        #    screens then show it as text (tests/e2e/test_security_xss.py)
        filename = name.replace("{tag}", tag)
        response = imports_steps.upload(api, filename, bank_statement.to_csv())
        if response.status_code == HTTPStatus.BAD_REQUEST:
            assert_error_includes(
                response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
            )
            return
        assert_that(
            (response.status_code, response.json()["batch"]["original-filename"])
        ).described_as(
            "an accepted name should be stored exactly as written, as plain text"
        ).is_equal_to((HTTPStatus.CREATED, filename))

    @pytest.mark.parametrize(
        "suffix", [".html", ".csv.exe", ".svg"], ids=["html", "double-extension", "svg"]
    )
    def test_only_csv_and_xlsx_are_read(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str, suffix: str
    ):
        # 1. Upload statement bytes with another extension
        # 2. Verification: 415 unsupported format
        response = imports_steps.upload(api, f"{tag}{suffix}", bank_statement.to_csv())
        assert_error_includes(
            response, HTTPStatus.UNSUPPORTED_MEDIA_TYPE, ImportErrorPayload.UNSUPPORTED_FORMAT
        )


@allure.feature("Security: upload")
class TestXmlAttacks(BaseApiTest):
    def test_an_external_entity_is_never_resolved(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload an XLSX whose sheet declares an external entity reading a system file
        # 2. Verification: 400 invalid structure, and nothing of that file in the answer
        doctype = f'<!DOCTYPE worksheet [<!ENTITY xxe SYSTEM "{SECRET_FILE}">]>'
        sheet = sheet_xml(tag, doctype=doctype, sender="&xxe;")
        response = upload_xlsx(api, tag, bank_statement, {SHEET: sheet})
        with soft_assertions():
            assert_error_includes(
                response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
            )
            assert_that(response.text).described_as(
                "no content of a server file should come back"
            ).does_not_contain(SECRET_MARKER)

    def test_an_entity_expansion_bomb_is_refused_quickly(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload an XLSX whose sheet holds a billion-laughs entity chain
        # 2. Verification: 400 invalid structure, answered within seconds
        sheet = sheet_xml(tag, doctype=billion_laughs(), sender="&lol9;")
        started = time.monotonic()
        response = upload_xlsx(api, tag, bank_statement, {SHEET: sheet})
        elapsed = time.monotonic() - started
        with soft_assertions():
            assert_error_includes(
                response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
            )
            assert_that(elapsed).described_as("the entities should never be expanded").is_less_than(
                REFUSAL_SECONDS
            )


@allure.feature("Security: upload")
class TestArchiveAttacks(BaseApiTest):
    def test_a_zip_bomb_is_refused(self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str):
        # 1. Upload an XLSX whose sheet expands more than a hundredfold (megabytes of blanks)
        # 2. Verification: 413 resource limit
        padding = " " * (4 * 1024 * 1024)
        sheet = sheet_xml(tag).replace("</worksheet>", f"{padding}</worksheet>")
        response = upload_xlsx(api, tag, bank_statement, {SHEET: sheet})
        assert_error_includes(
            response, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, ImportErrorPayload.RESOURCE_LIMIT
        )

    def test_an_archive_with_too_many_entries_is_refused(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload an XLSX with more entries than the reader allows (extra document parts)
        # 2. Verification: 413 resource limit
        extra = {f"docProps/qa{n}.xml": f"<qa n='{n}'/>" for n in range(ZIP_ENTRY_LIMIT)}
        response = upload_xlsx(api, tag, bank_statement, extra)
        assert_error_includes(
            response, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, ImportErrorPayload.RESOURCE_LIMIT
        )

    def test_a_path_traversal_entry_is_refused(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload an XLSX with an entry named to escape the archive ("../")
        # 2. Verification: 400 invalid structure
        response = upload_xlsx(
            api, tag, bank_statement, {"xl/worksheets/../../../qa-escape.xml": "<qa/>"}
        )
        assert_error_includes(
            response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
        )

    @pytest.mark.parametrize(
        "parts",
        [
            pytest.param({"xl/vbaProject.bin": "macro"}, id="macro-project"),
            pytest.param(
                {
                    "xl/_rels/workbook.xml.rels": (
                        "<Relationships xmlns='http://schemas.openxmlformats.org/package/"
                        "2006/relationships'><Relationship Id='rId1' Type='http://schemas."
                        "openxmlformats.org/officeDocument/2006/relationships/worksheet'"
                        " Target='worksheets/sheet1.xml'/><Relationship Id='rId9'"
                        " Type='http://schemas.openxmlformats.org/officeDocument/2006/"
                        "relationships/externalLink' Target='http://example.invalid/x.xlsx'"
                        " TargetMode='External'/></Relationships>"
                    )
                },
                id="external-link",
            ),
        ],
    )
    def test_macros_and_external_links_are_refused(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str, parts: dict[str, str]
    ):
        # 1. Upload an XLSX with a macro project or an external link
        # 2. Verification: 400 unsupported format
        response = upload_xlsx(api, tag, bank_statement, parts)
        assert_error_includes(
            response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.UNSUPPORTED_FORMAT
        )


# --- file-local helpers -------------------------------------------------------
def sheet_xml(tag: str, *, doctype: str = "", sender: str | None = None) -> str:
    """A one-row sheet; ``sender`` (default: a tagged name) may reference an entity."""
    who = sender if sender is not None else f"Jan Testowy {tag}"
    cells = "".join(
        f"<c r='{ref}' t='inlineStr'><is><t>{value}</t></is></c>"
        for ref, value in (
            ("A1", "2026-01-15"),
            ("B1", who),
            ("C1", f"Darowizna {tag}"),
            ("D1", "10,00"),
        )
    )
    return f"<?xml version='1.0'?>{doctype}<worksheet xmlns='{MAIN_NS}'><sheetData><row r='1'>{cells}</row></sheetData></worksheet>"  # noqa: E501


def upload_raw_name(api: AlmaSpeiApi, filename: bytes, content: bytes):
    """A bank CSV upload whose multipart file name bytes are sent exactly as given."""
    boundary = "qa-raw-boundary"
    fields = b"".join(
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in (("source", "bank"), ("separator", ";"))
    )
    file_part = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="'.encode()
        + filename
        + b'"\r\nContent-Type: text/csv\r\n\r\n'
        + content
        + f"\r\n--{boundary}--\r\n".encode()
    )
    return api.session.post(
        ApiPath.IMPORT_UPLOAD,
        content=fields + file_part,
        headers={Header.CONTENT_TYPE: f"multipart/form-data; boundary={boundary}"},
    )


def upload_xlsx(api: AlmaSpeiApi, tag: str, statement: BankStatement, parts: dict[str, str]):
    """Upload the statement as XLSX with ``parts`` added or replaced in the archive."""
    original = zipfile.ZipFile(io.BytesIO(statement.to_xlsx()))
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in original.namelist():
            archive.writestr(name, parts.get(name, original.read(name)))
        for name, text in parts.items():
            if name not in original.namelist():
                archive.writestr(name, text)
    return imports_steps.upload(api, f"{tag}.xlsx", buffer.getvalue(), separator=None)
