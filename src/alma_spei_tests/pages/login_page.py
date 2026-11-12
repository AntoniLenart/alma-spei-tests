"""Page object for the auth panel: login, forced password change, signed-in nav.

Mirrors src/ui/alma_spei/ui/auth/views.cljs. The panel lives on the root page
under the shell; which part it renders depends on the session:

* no user                     -> "Logowanie" form;
* password-change-required    -> "Zmiana hasła" form + logout only;
* signed in                   -> "Zalogowano: <display name>", nav, Start screen.
"""

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

    SIGNED_IN_PREFIX = "Zalogowano: "
    LOGOUT_BUTTON = "Wyloguj się"
    ACCOUNTS_NAV = "Konta użytkowników"
    HOME_HEADING = "Start"


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

    # --- signed-in chrome -----------------------------------------------------
    def signed_in_banner(self, display_name: str) -> Locator:
        return self.page.get_by_text(f"{AuthMessages.SIGNED_IN_PREFIX}{display_name}", exact=True)

    @property
    def home_heading(self) -> Locator:
        return self.page.get_by_role("heading", name=AuthMessages.HOME_HEADING, exact=True)

    @property
    def accounts_nav(self) -> Locator:
        return self.page.get_by_role("button", name=AuthMessages.ACCOUNTS_NAV)

    @property
    def logout_button(self) -> Locator:
        return self.page.get_by_role("button", name=AuthMessages.LOGOUT_BUTTON)
