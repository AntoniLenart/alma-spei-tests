"""Page object for the Alma Spei application shell (the Polish root page).

Mirrors src/ui/alma_spei/ui/views.cljs. On load the app dispatches
``:app/initialize`` which fetches ``/api/health/ready`` and renders one of the
Polish status messages below into the shell's ``role="status"`` live region (a
direct child of ``<main>``; the auth panel and donor views have their own
status regions deeper in the tree).
"""

from playwright.sync_api import Locator, expect

from alma_spei_tests.pages.base_page import BasePage


class ShellMessages:
    """The exact Polish strings the shell renders per health status."""

    LOADING = "Sprawdzanie połączenia…"
    OK = "Aplikacja jest gotowa."
    UNAVAILABLE = "Połączenie z bazą danych jest niedostępne. Spróbuj ponownie."
    INVALID = "Nie udało się odczytać odpowiedzi serwera."


class AppPage(BasePage):
    path = "/"

    HEADING = "Alma Spei"
    SUBTITLE = "Baza darczyńców"
    RECHECK_LABEL = "Sprawdź ponownie"
    EXPECTED_TITLE = "Alma Spei — Baza darczyńców"

    # --- locators -------------------------------------------------------------
    @property
    def heading(self) -> Locator:
        return self.page.get_by_role("heading", name=self.HEADING, exact=True)

    @property
    def subtitle(self) -> Locator:
        return self.page.get_by_text(self.SUBTITLE, exact=True)

    @property
    def status(self) -> Locator:
        return self.page.locator('main > p[role="status"]')

    @property
    def recheck_button(self) -> Locator:
        return self.page.get_by_role("button", name=self.RECHECK_LABEL)

    # --- queries / interactions ----------------------------------------------
    def status_text(self) -> str:
        return self.status.inner_text()

    def wait_for_status(self, text: str, timeout: float = 15_000):
        """Wait until the status region shows the given Polish message."""
        expect(self.status).to_have_text(text, timeout=timeout)

    def click_recheck(self):
        self.recheck_button.click()
