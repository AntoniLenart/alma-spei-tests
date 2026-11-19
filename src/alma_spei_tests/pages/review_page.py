"""Page object for the import review screen (tasks 37-38).

Mirrors src/ui/alma_spei/ui/imports/review_views.cljs and decision_views.cljs.
Reached from the sidebar ("Do weryfikacji"), the Start screen ("Wznów
weryfikację"), the upload report's "Przejdź do weryfikacji" link, or a deep link
``/#review/<batch-id>/<offset>``. It shows the
queue of bank batches awaiting review, then a batch with a row picker, the
source row, a donor search and the chosen donor's current profile. Below them
(task 38) the decision editor saves an explicit decision per row, donor
proposals are prepared, and an immutable preview of the whole import is built.
"""

import re

from playwright.sync_api import Locator

from alma_spei_tests.pages.base_page import BasePage
from alma_spei_tests.pages.login_page import LoginPage


class ReviewMessages:
    """Exact Polish strings of the review screen."""

    NAV = "Do weryfikacji"
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

    # decision editor (task 38)
    EDITOR_HEADING = "Decyzja dla bieżącego wiersza"
    CHOOSE_COMPARED = "Wybierz porównany profil do decyzji"
    NEW_PROFILE = "Przygotuj nowy profil"
    USE_PROPOSAL = "Użyj tej propozycji"
    SAVE_PROPOSAL = "Zapisz propozycję profilu"
    CHECKED_EXISTING = "Sprawdzono istniejące profile w bazie."
    CHECKED_PROPOSALS = (
        "Sprawdzono propozycje w tym imporcie; nie tworzę niepotrzebnego drugiego profilu."
    )
    PROPOSAL_SAVED = "Propozycję zapisano. Wybierz ją jawnie, aby użyć aktualnej wersji w decyzji."
    OVERLAP_CHECKED = (
        "Potwierdzam sprawdzenie nakładania się źródeł oraz odróżnienie duplikatu"
        " od rzeczywiście odrębnej, identycznej wpłaty."
    )
    SAVE_DECISION = "Zapisz decyzję dla wiersza"
    TARGET_EXISTING = "Profil w bazie"
    TARGET_PROPOSAL = "Proponowany nowy profil"
    COMPLETE = "decyzja kompletna; gotowość sprawdzana w podglądzie"
    ARCHIVED_NOT_SELECTABLE = (
        "Profil archiwalny służy do porównania. Nie można przypisać mu nowej wpłaty w tym kroku."
    )

    # preview (task 38)
    PREPARE_PREVIEW = "Przygotuj podgląd importu"
    PREVIEW_BLOCKED = "Podgląd wymaga uzupełnienia lub odświeżenia decyzji. Sprawdź listę braków."
    #: Readiness blocker messages (contracts/decisions.cljc ``blocker-messages``).
    BLOCKER_MESSAGES = {
        "invalid-row": "Wiersz zawiera błędy odczytu. Popraw plik źródłowy.",
        "stale-catalog": (
            "Baza darczyńców lub wpłat zmieniła się. Wczytaj, sprawdź i zapisz decyzję ponownie."
        ),
        "missing-decision": "Brakuje pełnej decyzji o darczyńcy i wpłacie.",
        "unsupported-amount": "Kwota ujemna wymaga ustalenia zasad zwrotów.",
        "stale-target": "Profil lub propozycja zmieniły się. Zweryfikuj decyzję ponownie.",
        "inactive-donor": "Wybrany profil jest archiwalny.",
        "duplicate-mismatch": "Wskazana wpłata nie odpowiada faktom z tego wiersza.",
    }

    @staticmethod
    def progress(reviewed: int, valid: int, invalid: int) -> str:
        return (
            f"Zapisane kompletne decyzje: {reviewed} z {valid} poprawnych wierszy."
            f" Wiersze z błędami: {invalid}."
        )

    @staticmethod
    def target(kind_label: str, name: str) -> str:
        return f"Cel decyzji: {kind_label} · {name}"

    @staticmethod
    def preview_summary(new_donors: int, new_payments: int, duplicates: int) -> str:
        return (
            f"Nowe profile: {new_donors}, nowe wpłaty: {new_payments},"
            f" już ujęte wpłaty: {duplicates}."
        )

    @staticmethod
    def preview_total(amount: str, currency: str) -> str:
        """``amount`` as the API reports it (dot decimal); the screen shows a comma."""
        return f"Nowe wpłaty: {amount.replace('.', ',')} {currency}"

    @staticmethod
    def blockers_count(total: int) -> str:
        return f"Wiersze wymagające uzupełnienia: {total}"

    @staticmethod
    def blocker(row: int, message: str, worksheet: int = 1) -> str:
        return f"Arkusz {worksheet}, wiersz {row}: {message}"

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

    # --- decision editor (task 38) --------------------------------------------
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
    def saved_notice(self) -> Locator:
        return self.editor.locator("p.decision-saved")

    @property
    def target_line(self) -> Locator:
        return self.editor.get_by_text("Cel decyzji:")

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

    # --- donor proposal form ----------------------------------------------------
    @property
    def proposal_type_select(self) -> Locator:
        return self.page.locator("#proposal-type")

    def proposal_field(self, field: str) -> Locator:
        """A proposal input by its kebab-case field (``name``, ``city``, ...)."""
        return self.page.locator(f"#proposal-{field}")

    def proposal_check(self, label: str) -> Locator:
        return self.editor.get_by_role("checkbox", name=label)

    @property
    def saved_proposal(self) -> Locator:
        return self.editor.locator("[role='status']").filter(has_text=ReviewMessages.PROPOSAL_SAVED)

    # --- preview ----------------------------------------------------------------
    @property
    def preview_section(self) -> Locator:
        return self.page.locator("section.decision-preview")

    def preview_button(self, name: str) -> Locator:
        return self.preview_section.get_by_role("button", name=name, exact=True)

    @property
    def preview_alert(self) -> Locator:
        return self.preview_section.get_by_role("alert")

    @property
    def blocker_items(self) -> Locator:
        return self.preview_section.locator("[role='status'] li")

    def preview_text(self, text: str) -> Locator:
        return self.preview_section.get_by_text(text, exact=True)

    @property
    def preview_items(self) -> Locator:
        return self.preview_section.locator("article.preview-item")


def _exactly(text: str) -> re.Pattern[str]:
    """A whole-text match for ``has_text`` (which otherwise matches substrings)."""
    return re.compile(rf"^\s*{re.escape(text)}\s*$")
