"""Page object for the import review screen (task 37).

Mirrors src/ui/alma_spei/ui/imports/review_views.cljs. Reached from the nav
("Weryfikacja importów"), the upload report's "Przejdź do weryfikacji" link, or
a deep link ``/#review/<batch-id>/<offset>``. It shows the queue of bank
batches awaiting review, then a batch with a row picker, the source row, a
donor search and the chosen donor's current profile - read-only.
"""

import re

from playwright.sync_api import Locator

from alma_spei_tests.pages.base_page import BasePage
from alma_spei_tests.pages.login_page import LoginPage


class ReviewMessages:
    """Exact Polish strings of the review screen."""

    NAV = "Weryfikacja importów"
    HEADING = "Weryfikacja importów"
    QUEUE_HEADING = "Importy oczekujące na weryfikację"
    OPEN_FROM_UPLOAD = "Przejdź do weryfikacji"
    BACK_TO_QUEUE = "Wróć do kolejki"
    SEARCH_BUTTON = "Szukaj darczyńcy"
    NO_DONOR_YET = (
        "Wyszukaj darczyńcę i wybierz „Porównaj”. Żaden profil nie jest wybierany automatycznie."
    )
    INVALID_ROW_NOTICE = (
        "Wiersz zawiera błędy. Samo porównanie nie usuwa błędów ani nie zatwierdza danych."
    )
    UNKNOWN_CURRENCY = "Nieustalona"
    ACTIVE = "Aktywny"
    ARCHIVED = "Archiwalny"

    # source card <dt> labels
    SOURCE_DATE = "Data w pliku"
    SOURCE_SENDER = "Nadawca i adres (oryginalny tekst)"
    SOURCE_DESCRIPTION = "Opis"
    SOURCE_AMOUNT = "Kwota w pliku"
    CURRENCY = "Waluta"

    # donor card <dt> labels (labels.cljs ``fields`` plus Typ/Status)
    DONOR_TYPE = "Typ"
    DONOR_NAME = "Nazwa / imię i nazwisko"
    DONOR_CITY = "Miejscowość"
    DONOR_STATUS = "Status"

    @staticmethod
    def progress(reviewed: int, valid: int, invalid: int) -> str:
        return (
            f"Zweryfikowane: {reviewed} z {valid} poprawnych wierszy. Wiersze z błędami: {invalid}."
        )

    @staticmethod
    def source_location(row: int, worksheet: int = 1) -> str:
        return f"Arkusz {worksheet}, wiersz {row}"

    @staticmethod
    def compare_label(name: str, city: str) -> str:
        return f"Porównaj profil {name}, {city}"

    @staticmethod
    def deep_link(batch_id: str, offset: int = 0) -> str:
        return f"/#review/{batch_id}/{offset}"


class ReviewPage(BasePage):
    path = "/"

    def open_from_nav(self) -> "ReviewPage":
        LoginPage(self.page).open()
        self.page.get_by_role("navigation").get_by_role(
            "button", name=ReviewMessages.NAV, exact=True
        ).click()
        return self

    def open_batch(self, batch_id: str) -> "ReviewPage":
        """Deep-link straight to a batch."""
        self.page.goto(ReviewMessages.deep_link(batch_id))
        return self

    # --- queue ----------------------------------------------------------------
    @property
    def heading(self) -> Locator:
        return self.page.get_by_role("heading", name=ReviewMessages.HEADING, exact=True, level=2)

    @property
    def queue_items(self) -> Locator:
        return self.page.locator("ul.review-batches > li")

    def queue_item(self, filename: str) -> Locator:
        return self.queue_items.filter(
            has=self.page.get_by_role("button", name=filename, exact=True)
        )

    def queue_button(self, filename: str) -> Locator:
        return self.queue_item(filename).get_by_role("button", name=filename, exact=True)

    def progress_text(self, scope: Locator | None = None) -> Locator:
        return (scope or self.page).locator(".review-progress [role='status']")

    # --- batch ----------------------------------------------------------------
    @property
    def batch_heading(self) -> Locator:
        return self.page.locator("#review-batch-heading")

    @property
    def row_select(self) -> Locator:
        return self.page.locator("#review-row")

    def select_row(self, row: int, worksheet: int = 1):
        self.row_select.select_option(f"{worksheet}:{row}")

    @property
    def source_card(self) -> Locator:
        return self.page.locator("section.review-source")

    @property
    def donor_card(self) -> Locator:
        return self.page.locator("section.review-donor")

    def card_value(self, card: Locator, label: str) -> Locator:
        return (
            card.locator("dl > div")
            .filter(has=self.page.locator("dt", has_text=_exactly(label)))
            .locator("dd")
        )

    def search_donor(self, text: str):
        self.page.locator("#review-search").fill(text)
        self.page.get_by_role("button", name=ReviewMessages.SEARCH_BUTTON).click()

    def compare_button(self, name: str, city: str) -> Locator:
        return self.page.get_by_role(
            "button", name=ReviewMessages.compare_label(name, city), exact=True
        )


def _exactly(text: str) -> re.Pattern[str]:
    """A whole-text match for ``has_text`` (which otherwise matches substrings)."""
    return re.compile(rf"^\s*{re.escape(text)}\s*$")
