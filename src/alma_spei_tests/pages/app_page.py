"""Page object for the Alma Spei application shell (the Polish root page).

Mirrors src/ui/alma_spei/ui/views.cljs. On load the app dispatches
``:app/initialize``, which fetches ``/api/health/ready``. A healthy app shows no
status at all: a ``role="status"`` connection notice with its "Sprawdź ponownie"
button appears only when the database is unavailable or the response cannot be
read. The shell also renders a "Przejdź do treści" skip link to the workspace
content, then the auth panel (see ``login_page``).
"""

from playwright.sync_api import Locator

from alma_spei_tests.pages.base_page import BasePage


class ShellMessages:
    """The exact Polish strings of the shell's connection notice."""

    UNAVAILABLE = "Połączenie z bazą danych jest niedostępne. Spróbuj ponownie."
    INVALID = "Nie udało się odczytać odpowiedzi serwera."


class AppPage(BasePage):
    path = "/"

    HEADING = "Alma Spei"
    SUBTITLE = "Baza darczyńców"
    RECHECK_LABEL = "Sprawdź ponownie"
    SKIP_LINK = "Przejdź do treści"
    EXPECTED_TITLE = "Alma Spei — Baza darczyńców"

    # --- locators -------------------------------------------------------------
    @property
    def heading(self) -> Locator:
        return self.page.get_by_role("heading", name=self.HEADING, exact=True)

    @property
    def subtitle(self) -> Locator:
        return self.page.get_by_text(self.SUBTITLE, exact=True)

    @property
    def connection_notice(self) -> Locator:
        return self.page.locator("div.connection-notice[role='status']")

    @property
    def notice_text(self) -> Locator:
        return self.connection_notice.locator("span")

    @property
    def recheck_button(self) -> Locator:
        return self.connection_notice.get_by_role("button", name=self.RECHECK_LABEL)

    @property
    def skip_link(self) -> Locator:
        return self.page.get_by_role("link", name=self.SKIP_LINK)

    @property
    def content(self) -> Locator:
        """The workspace/sign-in content the skip link moves focus to."""
        return self.page.locator("#workspace-content")
