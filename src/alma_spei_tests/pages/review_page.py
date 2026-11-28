"""Page object for the import review screen (tasks 37-38, automatic reconciliation).

Mirrors src/ui/alma_spei/ui/imports/review_views.cljs, automatic_views.cljs and
decision_views.cljs. Reached from the sidebar ("Do weryfikacji"), the Start
screen ("Wznów weryfikację"), a successful upload, or a deep link
``/#review/<batch-id>/<offset>``. Without a batch it lists the imports awaiting
review. A batch opens on its import summary: the source settings form (until
the file's currency is confirmed), then the automatic matching counts and total,
and either the approval step or the list of exceptions. "Wyjaśnij tę pozycję"
opens one exception beside its source row: the reviewer picks a donor from the
catalogue (search, compare, assign) or prepares a new one, and answers the
payment question only when the server still finds a possible duplicate.
"""

import re

from playwright.sync_api import Locator

from alma_spei_tests.pages.base_page import BasePage
from alma_spei_tests.pages.imports_page import CURRENT_STEP
from alma_spei_tests.pages.login_page import LoginPage


class ReviewMessages:
    """Exact Polish strings of the review screen."""

    NAV = "Do weryfikacji"
    #: The screen's <h2> per mode: the queue, a batch's summary, one exception.
    QUEUE_TITLE = "Importy do dokończenia"
    SUMMARY_TITLE = "Podsumowanie importu"
    EXCEPTION_TITLE = "Wyjaśnij niejednoznaczną pozycję"
    QUEUE_HEADING = "Importy oczekujące na weryfikację"
    #: The exception panel's own heading (``#review-batch-heading``).
    EXCEPTION_HEADING = "Pozycja wymagająca wyjaśnienia"
    SEARCH_BUTTON = "Szukaj darczyńcy"
    INVALID_ROW_NOTICE = (
        "Wiersz zawiera błędy. Samo porównanie nie usuwa błędów ani nie zatwierdza danych."
    )
    INVALID_ROW_ALERT = (
        "Ten przelew zawiera błędy. Popraw plik i prześlij poprawioną wersję jako nowy import."
        " Zmiana darczyńcy nie naprawi błędów źródłowych."
    )
    UNKNOWN_CURRENCY = "Nieustalona"
    ACTIVE = "Aktywny"

    # source settings (a batch staged without them)
    RUN_MATCHING = "Dopasuj i pokaż podsumowanie"

    # automatic summary <dt> labels
    MATCHED = "Dopasowane przelewy"
    NEW_DONORS = "Nowi darczyńcy"
    NEW_PAYMENTS = "Nowe wpłaty"
    DUPLICATES = "Potwierdzone duplikaty"
    EXCEPTIONS = "Do wyjaśnienia"
    READY_HEADING = "Wszystko gotowe do zatwierdzenia"
    REVIEW_CHANGES = "Sprawdź zmiany i zatwierdź"
    #: The transfers view of the summary (task 62): exceptions or exact matches.
    TRANSFERS_HEADING = "Weryfikacja przelewów"
    NO_EXACT_MATCHES = "Brak automatycznych dopasowań w 100%."
    EXPLAIN = "Wyjaśnij tę pozycję"
    NEXT_PAGE = "Następna strona"
    #: Why a transfer is an exception (automatic_views.cljs ``reasons``).
    REASONS = {
        "sender-format": "Nie można pewnie odczytać nazwy i adresu nadawcy.",
        "invalid-row": "Błędy w danych źródłowych — popraw plik.",
    }

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

    # donor choice of one exception
    THIS_DONOR = "To ten darczyńca"
    NEW_PROFILE_HINT = "Brak podobnych aktywnych profili. Sprawdź, czy dodać nowego darczyńcę."
    FROM_CATALOGUE = "Wybierz darczyńcę z bazy"
    NEW_DONOR = "Dodaj nowego darczyńcę"
    ASSIGN = "Przypisz wpłatę temu darczyńcy"
    ARCHIVED_NOTICE = "Ten profil jest archiwalny. Wybierz aktywnego darczyńcę."
    SAVE_PROPOSAL = "Zapisz i wybierz darczyńcę"
    CHECKED_EXISTING = "Sprawdzono istniejące profile w bazie."
    CHECKED_PROPOSALS = (
        "Sprawdzono nowych darczyńców przygotowanych w tym imporcie;"
        " ta osoba lub organizacja nie została dodana drugi raz."
    )

    # payment question (asked only for a possible duplicate)
    PAYMENT_LEGEND = "2. Sprawdź wpłatę"
    OVERLAP_CHECKED = (
        "Sprawdzono, czy ta wpłata nie została już uwzględniona z tego lub innego źródła."
        " Identyczna data i kwota nie wystarczają do uznania jej za duplikat."
    )
    SAVE_EXPLANATION = "Zapisz wyjaśnienie i wróć do podsumowania"
    #: What the editor still needs before saving (decision_views.cljs ``missing-checks``).
    MISSING_CURRENCY = "Podaj potwierdzoną walutę, np. PLN."
    MISSING_EVIDENCE = "Opisz, jak sprawdzono walutę i wcześniejsze ujęcie wpłaty."
    MISSING_DISPOSITION = "Wybierz, czy dodać wpłatę, czy wskazać już zapisaną."
    MISSING_OVERLAP = "Potwierdź sprawdzenie, czy wpłata nie została już uwzględniona."

    @staticmethod
    def progress(reviewed: int, valid: int, invalid: int) -> str:
        return (
            f"Sprawdzone przelewy: {reviewed} z {valid} poprawnych wierszy."
            f" Błędy w pliku: {invalid}."
        )

    @staticmethod
    def counts(
        *,
        matched: int = 0,
        new_donors: int = 0,
        new_payments: int = 0,
        duplicates: int = 0,
        exceptions: int = 0,
    ) -> dict[str, str]:
        """The summary's counts as shown, by label."""
        return {
            ReviewMessages.MATCHED: str(matched),
            ReviewMessages.NEW_DONORS: str(new_donors),
            ReviewMessages.NEW_PAYMENTS: str(new_payments),
            ReviewMessages.DUPLICATES: str(duplicates),
            ReviewMessages.EXCEPTIONS: str(exceptions),
        }

    @staticmethod
    def total(amount: str, currency: str) -> str:
        """``amount`` with a dot decimal, as the API reports it; the screen shows a comma."""
        return f"Do dodania: {amount.replace('.', ',')} {currency}"

    @staticmethod
    def exceptions_filter(total: int) -> str:
        return f"Do wyjaśnienia ({total})"

    @staticmethod
    def exact_filter(total: int) -> str:
        return f"Dopasowane w 100% ({total})"

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
        LoginPage(self.page).open().nav_button(ReviewMessages.NAV).click()
        return self

    def open_batch(self, batch_id: str) -> "ReviewPage":
        """Deep-link straight to a batch."""
        self.page.goto(ReviewMessages.deep_link(batch_id))
        return self

    # --- shared ---------------------------------------------------------------
    def screen_heading(self, text: str) -> Locator:
        """The screen's <h2>, which names the current mode."""
        return self.page.get_by_role("heading", name=text, exact=True, level=2)

    @property
    def current_step(self) -> Locator:
        return self.page.locator(CURRENT_STEP)

    @property
    def batch_id(self) -> str | None:
        """The batch in the address (``#review/<batch-id>/<offset>``), if any."""
        found = re.search(r"#review/([0-9a-f-]{36})/", self.page.url)
        return found.group(1) if found else None

    @property
    def batch_filename(self) -> Locator:
        """The file name in the bar above the summary or an exception."""
        return self.page.locator("div.review-batch-bar").locator("strong, span").first

    # --- queue ----------------------------------------------------------------
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

    # --- automatic summary ------------------------------------------------------
    @property
    def summary(self) -> Locator:
        return self.page.locator("section.automatic-summary")

    @property
    def idle_summary(self) -> Locator:
        """The summary once no matching or report request is in flight."""
        return self.page.locator("section.automatic-summary[aria-busy='false']")

    @property
    def settings_currency_input(self) -> Locator:
        return self.page.locator("#automatic-currency")

    @property
    def settings_donor_type_select(self) -> Locator:
        return self.page.locator("#automatic-type")

    def summary_button(self, name: str) -> Locator:
        return self.summary.get_by_role("button", name=name, exact=True)

    @property
    def counts(self) -> Locator:
        return self.summary.locator("dl.automatic-counts")

    def count_value(self, label: str) -> Locator:
        return (
            self.counts.locator("div")
            .filter(has=self.page.locator("dt", has_text=_exactly(label)))
            .locator("dd")
        )

    def count_values(self) -> dict[str, str]:
        """Every count of the summary, by its label."""
        pairs = self.counts.locator("div")
        return {
            pair.locator("dt").inner_text().strip(): pair.locator("dd").inner_text().strip()
            for pair in pairs.all()
        }

    @property
    def total_line(self) -> Locator:
        return self.summary.locator("p.automatic-total")

    @property
    def ready_card(self) -> Locator:
        return self.summary.locator("div.next-step-card")

    @property
    def exception_cards(self) -> Locator:
        return self.summary.locator("article.exception-card")

    def exception_card(self, text: str) -> Locator:
        """The exception card showing ``text`` (its sender or its reason)."""
        return self.exception_cards.filter(has_text=text)

    def exception_texts(self) -> list[list[str]]:
        """Each card's sender, ``date · amount currency`` and reason, in order."""
        return [
            [line.strip() for line in card.locator("strong, p").all_inner_texts()]
            for card in self.exception_cards.all()
        ]

    def filter_button(self, name: str) -> Locator:
        """One view of the transfers ("Do wyjaśnienia (n)" or "Dopasowane w 100% (n)")."""
        return self.summary.get_by_role("group", name="Filtr przelewów").get_by_role(
            "button", name=name, exact=True
        )

    @property
    def queue_pager(self) -> Locator:
        return self.summary.get_by_role("navigation", name="Strony przelewów")

    # --- one exception: source row and donor choice ------------------------------
    @property
    def exception_heading(self) -> Locator:
        return self.page.locator("#review-batch-heading")

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

    @property
    def invalid_row_alert(self) -> Locator:
        return self.page.locator("div.guided-review-editor p[role='alert']")

    @property
    def donor_choice(self) -> Locator:
        return self.page.locator("section.donor-choice")

    def choice_button(self, name: str) -> Locator:
        return self.donor_choice.get_by_role("button", name=name, exact=True)

    @property
    def chosen_donor(self) -> Locator:
        return self.donor_choice.locator("div.chosen-donor")

    @property
    def candidate_cards(self) -> Locator:
        """The suggested donors of the exception, strongest first."""
        return self.donor_choice.locator("div.review-candidates article.review-proposal")

    def candidate_card(self, name: str) -> Locator:
        return self.candidate_cards.filter(has=self.page.locator("strong", has_text=_exactly(name)))

    @property
    def status_filter_select(self) -> Locator:
        """The donor search's profile status filter (``active``/``archived``/``all``)."""
        return self.page.locator("#review-donor-status")

    def search_donor(self, text: str):
        self.page.locator("#review-search").fill(text)
        self.page.get_by_role("button", name=ReviewMessages.SEARCH_BUTTON).click()

    def compare_button(self, name: str, city: str) -> Locator:
        return self.page.get_by_role(
            "button", name=ReviewMessages.compare_label(name, city), exact=True
        )

    # --- new donor form ---------------------------------------------------------
    @property
    def proposal_type_select(self) -> Locator:
        return self.page.locator("#proposal-type")

    def proposal_field(self, field: str) -> Locator:
        """A proposal input by its kebab-case field (``name``, ``city``, ...)."""
        return self.page.locator(f"#proposal-{field}")

    def proposal_check(self, label: str) -> Locator:
        return self.page.locator("form.decision-proposal-form").get_by_role("checkbox", name=label)

    # --- decision editor (payment question) -------------------------------------
    @property
    def editor(self) -> Locator:
        return self.page.locator("section.decision-editor")

    @property
    def idle_editor(self) -> Locator:
        """The editor once its row decision is loaded and no save is in flight."""
        return self.page.locator("section.decision-editor[aria-busy='false']")

    def editor_button(self, name: str) -> Locator:
        return self.editor.get_by_role("button", name=name, exact=True)

    @property
    def payment_form(self) -> Locator:
        return self.editor.locator("fieldset").filter(
            has=self.page.locator("legend", has_text=_exactly(ReviewMessages.PAYMENT_LEGEND))
        )

    @property
    def currency_input(self) -> Locator:
        return self.page.locator("#decision-currency")

    @property
    def evidence_input(self) -> Locator:
        return self.page.locator("#decision-evidence")

    @property
    def disposition_select(self) -> Locator:
        return self.page.locator("#decision-disposition")

    @property
    def overlap_checkbox(self) -> Locator:
        return self.editor.get_by_role("checkbox", name=ReviewMessages.OVERLAP_CHECKED)

    @property
    def missing_checks(self) -> Locator:
        """What the editor still needs before the explanation can be saved."""
        return self.editor.locator("div.review-checklist[role='status'] li")


def _exactly(text: str) -> re.Pattern[str]:
    """A whole-text match for ``has_text`` (which otherwise matches substrings)."""
    return re.compile(rf"^\s*{re.escape(text)}\s*$")
