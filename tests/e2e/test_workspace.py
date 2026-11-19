"""E2E tests for the signed-in workspace: the Start screen and the sidebar.

The browser borrows the administrator's API session. The Start screen offers the
main tasks as cards ("Znajdź darczyńcę", "Importuj przelewy") and the resume
actions ("Wznów weryfikację", "Historia importów"); the sidebar marks the current
screen, and on a narrow screen folds its menu behind a "Menu" toggle.
"""

from collections.abc import Callable

import allure
import pytest
from playwright.sync_api import Locator, Page, ViewportSize, expect

from alma_spei_tests.pages import (
    AuthMessages,
    DonorListPage,
    ExecutionMessages,
    ExecutionPage,
    ImportsPage,
    LoginPage,
    ReviewPage,
)
from alma_spei_tests.testbase import BaseE2ETest

#: A phone-sized viewport, below the 45rem breakpoint where the menu folds.
NARROW_VIEWPORT: ViewportSize = {"width": 390, "height": 844}


@allure.feature("Workspace UI")
class TestStartScreen(BaseE2ETest):
    @pytest.mark.parametrize(
        ("task", "screen_heading"),
        [
            pytest.param(
                AuthMessages.FIND_DONOR, lambda page: DonorListPage(page).heading, id="donors"
            ),
            pytest.param(
                AuthMessages.IMPORT_TRANSFERS,
                lambda page: ImportsPage(page).heading,
                id="new-import",
            ),
            pytest.param(
                AuthMessages.RESUME_REVIEW, lambda page: ReviewPage(page).heading, id="review"
            ),
            pytest.param(
                AuthMessages.IMPORT_HISTORY,
                lambda page: ExecutionPage(page).heading(ExecutionMessages.HISTORY_HEADING),
                id="history",
            ),
        ],
    )
    def test_each_task_opens_its_screen(
        self,
        signed_in_page: Page,
        task: str,
        screen_heading: Callable[[Page], Locator],
    ):
        # 1. Open the app with the administrator's session (the Start screen)
        # 2. Choose one of the Start screen's tasks
        # 3. Verification: the screen of that task opens
        login = LoginPage(signed_in_page).open()
        expect(login.home_heading).to_be_visible()
        login.home_button(task).click()
        expect(screen_heading(signed_in_page)).to_be_visible()


@allure.feature("Workspace UI")
class TestSidebar(BaseE2ETest):
    def test_the_current_screen_is_marked_in_the_navigation(self, signed_in_page: Page):
        # 1. Open the app with the administrator's session
        # 2. Choose "Darczyńcy" in the sidebar
        # 3. Verification: "Darczyńcy" is marked as the current page, "Start" no longer is
        login = LoginPage(signed_in_page).open()
        expect(login.nav_button(AuthMessages.START_NAV)).to_have_attribute("aria-current", "page")
        login.donors_nav.click()
        expect(login.donors_nav).to_have_attribute("aria-current", "page")
        expect(login.nav_button(AuthMessages.START_NAV)).not_to_have_attribute(
            "aria-current", "page"
        )

    def test_a_narrow_screen_folds_the_menu_behind_a_toggle(self, signed_in_page: Page):
        # 1. Open the app with the administrator's session on a phone-sized screen
        # 2. Verify the menu is folded behind "Menu"
        # 3. Open the menu
        # 4. Verification: the navigation is shown and the toggle offers "Zamknij menu"
        signed_in_page.set_viewport_size(NARROW_VIEWPORT)
        login = LoginPage(signed_in_page).open()
        expect(login.menu_toggle).to_have_text(AuthMessages.OPEN_MENU)
        expect(login.main_nav).to_be_hidden()
        login.menu_toggle.click()
        expect(login.main_nav).to_be_visible()
        expect(login.menu_toggle).to_have_text(AuthMessages.CLOSE_MENU)
        expect(login.menu_toggle).to_have_attribute("aria-expanded", "true")
