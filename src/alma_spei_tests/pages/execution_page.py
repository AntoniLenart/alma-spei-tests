"""Page object for import confirmation, outcome, history and undo (task 40).

Mirrors src/ui/alma_spei/ui/imports/execution_views.cljs. Reached from the nav
("Historia importów"), the review preview's "Przejdź do zatwierdzenia" link, or
UUID-only fragments: ``#imports/history/<offset>``,
``#imports/confirm/<batch>/<preview>/<offset>``, ``#imports/batch/<batch>/<offset>``
and ``#imports/reimport/<batch>``. Nothing is written on opening a screen: the
backup receipt, the commit and the undo each need an explicit action.
"""

from playwright.sync_api import Locator

from alma_spei_tests.pages.base_page import BasePage
from alma_spei_tests.pages.login_page import LoginPage


class ExecutionMessages:
    """Exact Polish strings of the execution screens."""

    NAV_HISTORY = "Historia importów"
    HISTORY_HEADING = "Historia importów"
    OPEN_OUTCOME = "Otwórz wynik importu"
    GO_TO_CONFIRMATION = "Przejdź do zatwierdzenia"

    # confirmation
    CONFIRM_HEADING = "Zatwierdzenie importu"
    NO_FIELD_CHANGES = (
        "Istniejące profile pozostają bez zmian pól. Kwoty różnych walut nie są sumowane."
    )
    SYNTHETIC_MODE = (
        "Tryb testowy — nie powstaje rzeczywista kopia zapasowa."
        " Używaj wyłącznie danych syntetycznych."
    )
    REQUEST_BACKUP = "Poproś o testowe potwierdzenie kopii"
    CONSENT = (
        "Zatwierdzam cały wyświetlony podgląd. Potwierdzam użycie wyłącznie danych"
        " syntetycznych i rozumiem, że nie powstała rzeczywista kopia zapasowa."
    )
    COMMIT = "Zatwierdź import testowy"

    # outcome
    OUTCOME_HEADING = "Wynik importu"
    COMMITTED_SECTION = "Zapisane zatwierdzenie"
    UNDO = "Cofnij ostatni import"
    UNDO_HEADING = "Cofnąć ostatni import?"
    CANCEL_UNDO = "Anuluj cofnięcie"
    CONFIRM_UNDO = "Potwierdzam cofnięcie importu"
    UNDONE_HEADING = "Import został cofnięty"
    REIMPORT = "Wczytaj ten sam plik ponownie"
    REIMPORT_HEADING = "Nowa próba po cofnięciu importu"
    NOT_LATEST = "Można wycofać wyłącznie ostatni zatwierdzony import."

    # batch context <dt> labels and state labels
    FILE = "Plik"
    STATE = "Stan"
    UPLOADED_BY = "Przesłał(a)"
    STATE_COMMITTED = "Zapisany"
    STATE_UNDONE = "Cofnięty"

    @staticmethod
    def summary(new_donors: int, new_payments: int, duplicates: int) -> str:
        return (
            f"Nowe profile: {new_donors}, nowe wpłaty: {new_payments},"
            f" wpłaty już ujęte: {duplicates}."
        )

    @staticmethod
    def total(amount: str, currency: str) -> str:
        """``amount`` as the API reports it (dot decimal); the screen shows a comma."""
        return f"Nowe wpłaty: {amount.replace('.', ',')} {currency}"

    @staticmethod
    def committed_by(actor: str) -> str:
        return f"Zatwierdził(a): {actor}"

    @staticmethod
    def undo_counts(payments: int, donors: int) -> str:
        return (
            f"Wycofane wpłaty: {payments}, zarchiwizowane profile: {donors}."
            " Historia pozostaje zachowana."
        )

    @staticmethod
    def outcome_link(batch_id: str, offset: int = 0) -> str:
        return f"/#imports/batch/{batch_id}/{offset}"

    @staticmethod
    def confirm_link(batch_id: str, preview_id: str, offset: int = 0) -> str:
        return f"/#imports/confirm/{batch_id}/{preview_id}/{offset}"


class ExecutionPage(BasePage):
    path = "/"

    def open_history_from_nav(self) -> "ExecutionPage":
        LoginPage(self.page).open().nav_button(ExecutionMessages.NAV_HISTORY).click()
        return self

    def open_outcome(self, batch_id: str) -> "ExecutionPage":
        self.page.goto(ExecutionMessages.outcome_link(batch_id))
        return self

    def open_confirmation(self, batch_id: str, preview_id: str) -> "ExecutionPage":
        self.page.goto(ExecutionMessages.confirm_link(batch_id, preview_id))
        return self

    # --- shared ---------------------------------------------------------------
    @property
    def screen(self) -> Locator:
        return self.page.locator("section.execution-screen")

    def heading(self, text: str) -> Locator:
        return self.screen.get_by_role("heading", name=text, exact=True)

    def button(self, name: str) -> Locator:
        return self.screen.get_by_role("button", name=name, exact=True)

    def link(self, name: str) -> Locator:
        return self.screen.get_by_role("link", name=name, exact=True)

    def text(self, text: str) -> Locator:
        return self.screen.get_by_text(text, exact=True)

    def context_value(self, label: str, scope: Locator | None = None) -> Locator:
        """A ``dl.import-summary`` value by its <dt> label."""
        return (
            (scope or self.screen)
            .locator("dl.import-summary > div")
            .filter(has=self.page.locator("dt", has_text=label))
            .locator("dd")
        )

    # --- confirmation -----------------------------------------------------------
    @property
    def consent_checkbox(self) -> Locator:
        return self.page.locator("#execution-consent")

    @property
    def backup_status(self) -> Locator:
        return self.screen.locator("[role='status']").filter(has_text="Potwierdzenie testowe:")

    # --- history ----------------------------------------------------------------
    def history_entry(self, filename: str) -> Locator:
        return self.screen.locator("article.execution-history-entry").filter(
            has=self.page.get_by_role("heading", name=filename, exact=True)
        )

    # --- undo -------------------------------------------------------------------
    @property
    def undo_dialog(self) -> Locator:
        return self.page.locator("dialog.execution-dialog")

    def dialog_button(self, name: str) -> Locator:
        return self.undo_dialog.get_by_role("button", name=name, exact=True)
