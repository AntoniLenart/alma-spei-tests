"""E2E tests for the Polish application shell.

On load the shell checks ``/api/health/ready`` and renders a Polish status. With
the orchestrated stack healthy, it must settle on "Aplikacja jest gotowa.".
"""

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.pages.app_page import AppPage, ShellMessages
from alma_spei_tests.steps import ui_steps
from alma_spei_tests.testbase import BaseE2ETest


@allure.feature("Application shell")
class TestApplicationShell(BaseE2ETest):
    @pytest.mark.smoke
    def test_shell_shows_title_and_header(self, app_page: AppPage):
        # 1. Open the application shell
        # 2. Verification: Polish document title and the Alma Spei / Baza darczyńców header
        app_page.open()
        with soft_assertions():
            assert_that(app_page.title()).described_as(
                "document title should be the Polish application title"
            ).is_equal_to(AppPage.EXPECTED_TITLE)
            assert_that(app_page.heading.is_visible()).described_as(
                "the 'Alma Spei' header should be visible"
            ).is_true()
            assert_that(app_page.subtitle.is_visible()).described_as(
                "the 'Baza darczyńców' subtitle should be visible"
            ).is_true()

    @pytest.mark.smoke
    def test_shell_reports_application_ready(self, app_page: AppPage):
        # 1. Open the application shell
        # 2. Wait for the health check to resolve
        # 3. Verification: the status region shows the Polish ready message
        app_page.open()
        app_page.wait_for_status(ShellMessages.OK)
        assert_that(app_page.status_text()).described_as(
            "the shell should report that the application is ready"
        ).is_equal_to(ShellMessages.OK)

    def test_recheck_button_keeps_application_ready(self, app_page: AppPage):
        # 1. Open the application shell and wait until it is ready
        # 2. Trigger a manual connection re-check
        # 3. Verification: the shell settles back on the ready message
        app_page.open()
        app_page.wait_for_status(ShellMessages.OK)
        ui_steps.trigger_recheck(app_page)
        app_page.wait_for_status(ShellMessages.OK)
        assert_that(app_page.status_text()).described_as(
            "the shell should remain ready after a re-check"
        ).is_equal_to(ShellMessages.OK)
