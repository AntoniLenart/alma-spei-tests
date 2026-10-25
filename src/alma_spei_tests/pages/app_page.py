"""Page object for the Alma Spei application shell (the Polish root page).

Mirrors src/ui/alma_spei/ui/views.cljs. On load the app dispatches
``:app/initialize`` which fetches ``/api/health/ready`` and renders one of the
Polish status messages below into the ``role="status"`` live region.
"""

from playwright.sync_api import Locator, Page, expect


class ShellMessages:
    """The exact Polish strings the shell renders per health status."""

    LOADING = "Sprawdzanie połączenia…"
    OK = "Aplikacja jest gotowa."
    UNAVAILABLE = "Połączenie z bazą danych jest niedostępne. Spróbuj ponownie."
    INVALID = "Nie udało się odczytać odpowiedzi serwera."


class AppPage:
    path = "/"

    # Expected static content
    HEADING = "Alma Spei"
    SUBTITLE = "Baza darczyńców"
    RECHECK_LABEL = "Sprawdź ponownie"
    EXPECTED_TITLE = "Alma Spei — Baza darczyńców"

    def __init__(self, page: Page):
        self.page = page

    # --- navigation -----------------------------------------------------------
    def open(self) -> "AppPage":
        self.page.goto(self.path)
        return self

    # --- locators -------------------------------------------------------------
    @property
    def heading(self) -> Locator:
        return self.page.get_by_role("heading", name=self.HEADING)

    @property
    def subtitle(self) -> Locator:
        return self.page.get_by_text(self.SUBTITLE, exact=True)

    @property
    def status(self) -> Locator:
        return self.page.get_by_role("status")

    @property
    def recheck_button(self) -> Locator:
        return self.page.get_by_role("button", name=self.RECHECK_LABEL)

    # --- queries / interactions ----------------------------------------------
    def title(self) -> str:
        return self.page.title()

    def status_text(self) -> str:
        return self.status.inner_text()

    def wait_for_status(self, text: str, timeout: float = 15_000):
        """Wait until the status region shows the given Polish message."""
        expect(self.status).to_have_text(text, timeout=timeout)

    def click_recheck(self):
        self.recheck_button.click()
