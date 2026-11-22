"""Page object for the bank upload screen (task 36, guided import review).

Mirrors src/ui/alma_spei/ui/imports/views.cljs. The screen is reached from the
sidebar ("Nowy import") or the Start screen ("Importuj przelewy") and shows the
import steps and the upload form: the file, the CSV separator and the source
settings confirmed once per file (currency, optionally the type of new donors).
A successful upload hands those settings to the automatic matching and opens the
import summary on the review screen; a rejected or failed analysis stays here
with its alert (and, for a failed batch, its summary and a confirmed retry).
"""

import re

from playwright.sync_api import Locator

from alma_spei_tests.pages.base_page import BasePage
from alma_spei_tests.pages.login_page import LoginPage

#: The step shown as current in the shared import step indicator.
CURRENT_STEP = "ol.import-steps li[aria-current='step']"


class ImportMessages:
    """Exact Polish strings of the upload screen."""

    NAV = "Nowy import"
    HEADING = "Import przelewów"
    SYNTHETIC_NOTE = "Wersja testowa. Używaj wyłącznie danych syntetycznych."
    #: The import steps, in order; the current one is marked ``aria-current="step"``.
    STEPS = ("Plik", "Sprawdzenie danych", "Dopasowanie", "Podsumowanie", "Zatwierdzenie")
    UPLOAD_BUTTON = "Prześlij i dopasuj automatycznie"
    RETRY_BUTTON = "Ponów analizę tego samego pliku"
    RETRY_CONFIRMATION = "Potwierdzam ponowną analizę tego samego pliku."

    # summary <dt> labels (shown for a failed batch)
    ATTEMPT = "Próba"
    STATUS = "Status"

    # batch state labels
    STATE_FAILED = "Analiza zakończona błędem"

    # alerts
    WRONG_FILE_TYPE = "Wybierz plik CSV lub XLSX."
    DUPLICATE = (
        "Ten plik został już przesłany, także jeśli wcześniej miał inną nazwę. "
        "Kolejny import nie został utworzony."
    )
    OPEN_HISTORY = "Otwórz historię importów"
    INVALID_FILE = (
        "Nie można odczytać pliku. Sprawdź układ czterech kolumn, daty i kwoty. "
        "Formuły nie są obsługiwane."
    )


class ImportsPage(BasePage):
    path = "/"

    def open_from_nav(self) -> "ImportsPage":
        """Open the app and switch to the upload screen."""
        LoginPage(self.page).open().nav_button(ImportMessages.NAV).click()
        return self

    # --- import steps -----------------------------------------------------------
    @property
    def step_labels(self) -> Locator:
        """The step names, without their numbers."""
        return self.page.get_by_role("list", name="Etapy importu").locator(
            "li > span:not(.step-number)"
        )

    @property
    def current_step(self) -> Locator:
        return self.page.locator(CURRENT_STEP)

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
    def currency_input(self) -> Locator:
        """The file's currency, confirmed once for every transfer in it."""
        return self.page.locator("#import-currency")

    @property
    def donor_type_select(self) -> Locator:
        """The optional type of new donors in this file (blank: ask for each)."""
        return self.page.locator("#import-donor-type")

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

    @property
    def alert_message(self) -> Locator:
        """The alert's text without its links (task 40 adds a history link to some)."""
        return self.alert.locator("p")

    @property
    def history_link(self) -> Locator:
        return self.alert.get_by_role("link", name=ImportMessages.OPEN_HISTORY)

    def choose_file(self, filename: str, content: bytes):
        self.file_input.set_input_files(
            {"name": filename, "mimeType": "application/octet-stream", "buffer": content}
        )

    def choose_separator(self, separator: str):
        self.separator_select.select_option(separator)

    # --- summary of a failed batch ----------------------------------------------
    def summary_value(self, label: str) -> Locator:
        return (
            self.page.locator("dl.import-summary > div")
            .filter(has=self.page.locator("dt", has_text=_exactly(label)))
            .locator("dd")
        )


def _exactly(text: str) -> re.Pattern[str]:
    """A whole-text match for ``has_text`` (which otherwise matches substrings)."""
    return re.compile(rf"^\s*{re.escape(text)}\s*$")
