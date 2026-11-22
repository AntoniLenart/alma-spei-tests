"""Page object for the auth panel: login, password change and the signed-in workspace.

Mirrors src/ui/alma_spei/ui/auth/views.cljs. The panel lives on the root page
under the shell; which part it renders depends on the session:

* no user                     -> sign-in shell with the "Logowanie" form;
* password-change-required    -> workspace with the sidebar account panel
                                 ("Zalogowano jako" + name, "Wyloguj się") but no
                                 navigation, and the "Zmiana hasła" form;
* signed in                   -> workspace: sidebar with the main navigation and
                                 the account panel, the "Od czego zaczynamy?" Start
                                 screen with its task cards.

Below 45rem the sidebar menu folds behind a "Menu" toggle.
"""

import re

from playwright.sync_api import Locator

from alma_spei_tests.pages.base_page import BasePage


class AuthMessages:
    """Exact Polish strings rendered by the auth panel."""

    LOGIN_HEADING = "Logowanie"
    USERNAME_LABEL = "Nazwa użytkownika"
    PASSWORD_LABEL = "Hasło"
    LOGIN_BUTTON = "Zaloguj się"

    PASSWORD_HEADING = "Zmiana hasła"
    TEMPORARY_NOTICE = "Przed rozpoczęciem pracy zmień hasło tymczasowe."
    CURRENT_PASSWORD_LABEL = "Obecne hasło"
    NEW_PASSWORD_LABEL = "Nowe hasło"
    CONFIRM_PASSWORD_LABEL = "Powtórz nowe hasło"
    CHANGE_PASSWORD_BUTTON = "Zmień hasło"
    PASSWORDS_DIFFER = "Nowe hasła muszą być takie same."
    PASSWORD_POLICY_FAILED = "Nowe hasło nie spełnia wymagań."

    SIGNED_IN_LABEL = "Zalogowano jako"
    LOGOUT_BUTTON = "Wyloguj się"

    # sidebar navigation ("Nawigacja główna")
    MAIN_NAV = "Nawigacja główna"
    START_NAV = "Start"
    DONORS_NAV = "Darczyńcy"
    NEW_IMPORT_NAV = "Nowy import"
    REVIEW_NAV = "Do weryfikacji"
    HISTORY_NAV = "Historia importów"
    CHANGE_PASSWORD_NAV = "Zmień hasło"
    ACCOUNTS_NAV = "Konta użytkowników"
    OPEN_MENU = "Menu"
    CLOSE_MENU = "Zamknij menu"
    #: The account panel's reminder that this installation holds invented data.
    DEMO_LABEL = "Wersja testowa · dane fikcyjne"

    # Start screen
    HOME_HEADING = "Od czego zaczynamy?"
    FIND_DONOR = "Znajdź darczyńcę"
    IMPORT_TRANSFERS = "Importuj przelewy"
    RESUME_REVIEW = "Wznów weryfikację"
    IMPORT_HISTORY = "Historia importów"


class LoginPage(BasePage):
    path = "/"

    # --- login form -----------------------------------------------------------
    @property
    def login_heading(self) -> Locator:
        return self.page.get_by_role("heading", name=AuthMessages.LOGIN_HEADING)

    @property
    def username_input(self) -> Locator:
        return self.page.get_by_label(AuthMessages.USERNAME_LABEL, exact=True)

    @property
    def password_input(self) -> Locator:
        return self.page.get_by_label(AuthMessages.PASSWORD_LABEL, exact=True)

    @property
    def login_button(self) -> Locator:
        return self.page.get_by_role("button", name=AuthMessages.LOGIN_BUTTON)

    @property
    def alert(self) -> Locator:
        return self.page.get_by_role("alert")

    def log_in(self, username: str, password: str):
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()

    # --- password change form ---------------------------------------------------
    @property
    def password_form(self) -> Locator:
        return self.page.locator("form").filter(
            has=self.page.get_by_role("heading", name=AuthMessages.PASSWORD_HEADING)
        )

    @property
    def temporary_notice(self) -> Locator:
        return self.page.get_by_text(AuthMessages.TEMPORARY_NOTICE, exact=True)

    def change_password(self, current: str, new: str, confirmation: str | None = None):
        form = self.password_form
        form.get_by_label(AuthMessages.CURRENT_PASSWORD_LABEL, exact=True).fill(current)
        form.get_by_label(AuthMessages.NEW_PASSWORD_LABEL, exact=True).fill(new)
        form.get_by_label(AuthMessages.CONFIRM_PASSWORD_LABEL, exact=True).fill(
            new if confirmation is None else confirmation
        )
        form.get_by_role("button", name=AuthMessages.CHANGE_PASSWORD_BUTTON).click()

    # --- signed-in workspace ---------------------------------------------------
    @property
    def account_panel(self) -> Locator:
        """The sidebar's "Zalogowano jako <name>" block with the logout button."""
        return self.page.locator(".sidebar-account")

    @property
    def demo_label(self) -> Locator:
        return self.account_panel.get_by_text(AuthMessages.DEMO_LABEL, exact=True)

    def signed_in_as(self, display_name: str) -> Locator:
        """The account panel's name, once it shows ``display_name``."""
        return self.account_panel.locator("strong").filter(has_text=_exactly(display_name))

    @property
    def main_nav(self) -> Locator:
        return self.page.get_by_role("navigation", name=AuthMessages.MAIN_NAV)

    def nav_button(self, label: str) -> Locator:
        return self.main_nav.get_by_role("button", name=label, exact=True)

    @property
    def menu_toggle(self) -> Locator:
        """The narrow-screen menu toggle ("Menu" / "Zamknij menu")."""
        return self.page.locator("button.sidebar-toggle")

    @property
    def home_heading(self) -> Locator:
        return self.page.get_by_role("heading", name=AuthMessages.HOME_HEADING, exact=True)

    def home_button(self, label: str) -> Locator:
        """A task button of the Start screen (task cards and "resume" actions)."""
        return self.page.locator("section.home-screen").get_by_role(
            "button", name=label, exact=True
        )

    @property
    def donors_nav(self) -> Locator:
        return self.nav_button(AuthMessages.DONORS_NAV)

    @property
    def accounts_nav(self) -> Locator:
        return self.nav_button(AuthMessages.ACCOUNTS_NAV)

    @property
    def logout_button(self) -> Locator:
        return self.account_panel.get_by_role("button", name=AuthMessages.LOGOUT_BUTTON)


def _exactly(text: str) -> re.Pattern[str]:
    """A whole-text match for ``has_text`` (which otherwise matches substrings)."""
    return re.compile(rf"^\s*{re.escape(text)}\s*$")
