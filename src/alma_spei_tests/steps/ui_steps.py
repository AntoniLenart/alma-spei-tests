"""Reusable steps for the Polish application shell."""

from playwright.sync_api import Page

from alma_spei_tests.pages import AppPage
from alma_spei_tests.pages.app_page import ShellMessages
from alma_spei_tests.steps import step


@step("Open the application shell")
def open_application(page: Page) -> AppPage:
    return AppPage(page).open()


@step("Wait for the shell to report readiness")
def wait_until_ready(app: AppPage) -> AppPage:
    app.wait_for_status(ShellMessages.OK)
    return app


@step("Trigger a connection re-check")
def trigger_recheck(app: AppPage) -> AppPage:
    app.click_recheck()
    return app
