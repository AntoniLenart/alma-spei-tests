"""Page object for the bank upload screen and its validation report (task 36).

Mirrors src/ui/alma_spei/ui/imports/views.cljs. The screen is reached from the
signed-in navigation ("Import przelewów") and shows, in turn, the upload form,
upload progress, the analysis summary and the paged row report.
"""

import re

from playwright.sync_api import Locator

from alma_spei_tests.pages.base_page import BasePage
from alma_spei_tests.pages.login_page import LoginPage


class ImportMessages:
    """Exact Polish strings of the upload screen."""

    NAV = "Import przelewów"
    HEADING = "Import przelewów bankowych"
    SYNTHETIC_NOTE = "Na tym etapie używaj wyłącznie danych syntetycznych."
    UPLOAD_BUTTON = "Prześlij do analizy"
    RETRY_BUTTON = "Ponów analizę tego samego pliku"
    RETRY_CONFIRMATION = "Potwierdzam ponowną analizę tego samego pliku."
    CHOOSE_ANOTHER = "Wybierz inny plik"
    NEXT_ROWS = "Następne wiersze"
    OPEN_REVIEW = "Przejdź do weryfikacji"
    REPORT_REGION = "Raport wierszy importu"
    INVALID_ROWS_NOTICE = (
        "Wiersze z błędami pozostają w raporcie. Wymagają wyjaśnienia przed zatwierdzeniem importu."
    )
    VALID_FORMAT = "Poprawny format"
    UNKNOWN_CURRENCY = "Nieustalona"

    # summary <dt> labels
    FILE = "Plik"
    ATTEMPT = "Próba"
    STATUS = "Status"
    TOTAL_ROWS = "Wiersze z danymi"
    VALID_ROWS = "Poprawne technicznie"
    INVALID_ROWS = "Wiersze z błędami"
    SKIPPED_ROWS = "Pominięte puste wiersze"

    # batch state labels
    STATE_REVIEW = "Oczekuje na weryfikację"
    STATE_FAILED = "Analiza zakończona błędem"

    # alerts
    WRONG_FILE_TYPE = "Wybierz plik CSV lub XLSX."
    DUPLICATE = (
        "Ten plik został już przesłany, także jeśli wcześniej miał inną nazwę. "
        "Kolejny import nie został utworzony."
    )
    INVALID_FILE = (
        "Nie można odczytać pliku. Sprawdź układ czterech kolumn, daty i kwoty. "
        "Formuły nie są obsługiwane."
    )

    @staticmethod
    def rows_summary(first: int, last: int, total: int) -> str:
        return f"Wiersze: {first}–{last} z {total}"

    @staticmethod
    def row_ref(row_number: int, worksheet: int = 1) -> str:
        return f"{worksheet} / {row_number}"


class ImportsPage(BasePage):
    path = "/"

    def open_from_nav(self) -> "ImportsPage":
        """Open the app and switch to the upload screen."""
        LoginPage(self.page).open()
        self.page.get_by_role("navigation").get_by_role(
            "button", name=ImportMessages.NAV, exact=True
        ).click()
        return self

    # --- form -----------------------------------------------------------------
    @property
    def heading(self) -> Locator:
        return self.page.get_by_role("heading", name=ImportMessages.HEADING, exact=True)

    @property
    def synthetic_note(self) -> Locator:
        return self.page.get_by_text(ImportMessages.SYNTHETIC_NOTE, exact=True)

    @property
    def file_input(self) -> Locator:
        return self.page.locator("#import-file")

    @property
    def separator_select(self) -> Locator:
        return self.page.locator("#import-separator")

    @property
    def upload_button(self) -> Locator:
        return self.page.get_by_role("button", name=ImportMessages.UPLOAD_BUTTON)

    @property
    def retry_button(self) -> Locator:
        return self.page.get_by_role("button", name=ImportMessages.RETRY_BUTTON)

    @property
    def retry_confirmation(self) -> Locator:
        return self.page.get_by_role("checkbox", name=ImportMessages.RETRY_CONFIRMATION)

    @property
    def alert(self) -> Locator:
        return self.page.locator("section.import-screen").get_by_role("alert")

    def choose_file(self, filename: str, content: bytes):
        self.file_input.set_input_files(
            {"name": filename, "mimeType": "application/octet-stream", "buffer": content}
        )

    def choose_separator(self, separator: str):
        self.separator_select.select_option(separator)

    # --- summary & report -----------------------------------------------------
    def summary_value(self, label: str) -> Locator:
        return (
            self.page.locator("dl.import-summary > div")
            .filter(has=self.page.locator("dt", has_text=_exactly(label)))
            .locator("dd")
        )

    @property
    def invalid_rows_notice(self) -> Locator:
        return self.page.get_by_text(ImportMessages.INVALID_ROWS_NOTICE, exact=True)

    @property
    def report_rows(self) -> Locator:
        return self.page.get_by_role("region", name=ImportMessages.REPORT_REGION).locator(
            "tbody tr:has(th[scope='row'])"
        )

    def report_row(self, row_number: int) -> Locator:
        return self.report_rows.filter(
            has=self.page.locator("th", has_text=_exactly(ImportMessages.row_ref(row_number)))
        )

    def report_cells(self, row_number: int) -> list[str]:
        return [t.strip() for t in self.report_row(row_number).locator("td").all_inner_texts()]

    def report_errors(self, row_number: int) -> list[str]:
        return [t.strip() for t in self.report_row(row_number).locator("li").all_inner_texts()]

    @property
    def rows_summary(self) -> Locator:
        return self.page.locator('nav.import-pagination [role="status"]')

    @property
    def review_link(self) -> Locator:
        """ "Przejdź do weryfikacji" - shown for a batch awaiting review (task 37)."""
        return self.page.get_by_role("link", name=ImportMessages.OPEN_REVIEW)

    @property
    def next_rows_button(self) -> Locator:
        return self.page.get_by_role("button", name=ImportMessages.NEXT_ROWS)


def _exactly(text: str) -> re.Pattern[str]:
    """A whole-text match for ``has_text`` (which otherwise matches substrings)."""
    return re.compile(rf"^\s*{re.escape(text)}\s*$")
