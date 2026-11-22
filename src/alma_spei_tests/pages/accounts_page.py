"""Page object for the account management panel (administrators only).

Mirrors the ``accounts`` and ``edit-form`` views in src/ui/alma_spei/ui/auth/views.cljs.
Reached from the sidebar ("Konta użytkowników", shown to administrators only).
The panel offers a "Nowe konto" form and one form per account (display name,
"Konto aktywne", "Zarządzanie kontami", "Zapisz", "Resetuj hasło"); saving and
resetting ask for a browser confirmation first. A new or reset account's
temporary password is shown once, in a status box with "Zamknij hasło".
"""

from playwright.sync_api import Locator

from alma_spei_tests.pages.base_page import BasePage
from alma_spei_tests.pages.login_page import LoginPage


class AccountMessages:
    """Exact Polish strings of the account panel."""

    NAV = "Konta użytkowników"
    HEADING = "Zarządzanie kontami"
    NEW_ACCOUNT = "Nowe konto"
    USERNAME = "Nazwa użytkownika (niezmienna)"
    DISPLAY_NAME = "Nazwa wyświetlana"
    ADMINISTRATOR = "Zarządzanie kontami"
    ACTIVE = "Konto aktywne"
    CREATE = "Utwórz konto"
    SAVE = "Zapisz"
    RESET_PASSWORD = "Resetuj hasło"
    TEMPORARY_PASSWORD_NOTICE = (
        "Hasło tymczasowe — przekaż je bezpiecznie."
        " Po zamknięciu nie będzie można go ponownie wyświetlić."
    )
    CLOSE_PASSWORD = "Zamknij hasło"


class AccountsPage(BasePage):
    path = "/"

    def open_from_nav(self) -> "AccountsPage":
        LoginPage(self.page).open().nav_button(AccountMessages.NAV).click()
        return self

    @property
    def heading(self) -> Locator:
        return self.page.get_by_role("heading", name=AccountMessages.HEADING, level=2)

    # --- new account ------------------------------------------------------------
    @property
    def create_form(self) -> Locator:
        return self.page.locator("form").filter(
            has=self.page.get_by_role("heading", name=AccountMessages.NEW_ACCOUNT, exact=True)
        )

    def create(self, username: str, display_name: str):
        form = self.create_form
        form.get_by_label(AccountMessages.USERNAME).fill(username)
        form.get_by_label(AccountMessages.DISPLAY_NAME).fill(display_name)
        form.get_by_role("button", name=AccountMessages.CREATE).click()

    # --- existing accounts ------------------------------------------------------
    def account_form(self, username: str) -> Locator:
        """The edit form of one account (headed by its username)."""
        return self.page.locator("form").filter(
            has=self.page.get_by_role("heading", name=username, exact=True)
        )

    def active_checkbox(self, username: str) -> Locator:
        return self.account_form(username).get_by_label(AccountMessages.ACTIVE)

    def account_button(self, username: str, name: str) -> Locator:
        return self.account_form(username).get_by_role("button", name=name, exact=True)

    # --- one-time temporary password ---------------------------------------------
    @property
    def temporary_password_box(self) -> Locator:
        return self.page.locator("aside[role='status']").filter(
            has_text=AccountMessages.TEMPORARY_PASSWORD_NOTICE
        )

    @property
    def temporary_password(self) -> Locator:
        return self.temporary_password_box.locator("output")

    @property
    def close_password_button(self) -> Locator:
        return self.temporary_password_box.get_by_role(
            "button", name=AccountMessages.CLOSE_PASSWORD
        )
