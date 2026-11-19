"""E2E tests for the Polish application shell.

On load the shell checks ``/api/health/ready``. A healthy app shows no status at
all; a connection notice with "Sprawdź ponownie" appears only when the database
is unavailable or the answer cannot be read. Those states are produced by routing
the browser's health check to a canned answer, so the backend stays untouched.
"""

import json
from http import HTTPStatus

import allure
import pytest
from assertpy import assert_that, soft_assertions
from playwright.sync_api import Page, expect

from alma_spei_tests.constants import HealthStatus
from alma_spei_tests.pages import AppPage, ShellMessages
from alma_spei_tests.steps import ui_steps
from alma_spei_tests.testbase import BaseE2ETest

#: The readiness probe's answer while the database is down.
UNAVAILABLE_BODY = json.dumps({"status": HealthStatus.UNAVAILABLE})
#: A readiness answer outside the health contract.
UNREADABLE_BODY = json.dumps({"status": "starting"})


@allure.feature("Application shell")
class TestApplicationShell(BaseE2ETest):
    @pytest.mark.smoke
    def test_shell_shows_title_and_header(self, page: Page):
        # 1. Open the application shell
        # 2. Verification: Polish document title and the Alma Spei / Baza darczyńców header
        app = ui_steps.open_application(page)
        with soft_assertions():
            assert_that(app.title()).described_as(
                "document title should be the Polish application title"
            ).is_equal_to(AppPage.EXPECTED_TITLE)
            assert_that(app.heading.is_visible()).described_as(
                "the 'Alma Spei' header should be visible"
            ).is_true()
            assert_that(app.subtitle.is_visible()).described_as(
                "the 'Baza darczyńców' subtitle should be visible"
            ).is_true()

    @pytest.mark.smoke
    def test_a_healthy_app_shows_no_connection_notice(self, page: Page):
        # 1. Open the application shell and wait for its health check
        # 2. Verification: no connection notice is shown
        app = ui_steps.open_application(page)
        expect(app.connection_notice).to_be_hidden()

    def test_an_unavailable_database_is_reported_with_a_recheck(self, page: Page):
        # 1. Make the readiness probe report the database as unavailable (HTTP 503)
        # 2. Open the application shell
        # 3. Verification: the Polish unavailable notice with its "Sprawdź ponownie" button
        ui_steps.fake_readiness(page, HTTPStatus.SERVICE_UNAVAILABLE, UNAVAILABLE_BODY)
        app = ui_steps.open_application(page)
        expect(app.notice_text).to_have_text(ShellMessages.UNAVAILABLE)
        expect(app.recheck_button).to_be_visible()

    def test_an_unreadable_answer_is_reported(self, page: Page):
        # 1. Make the readiness probe answer outside the health contract
        # 2. Open the application shell
        # 3. Verification: the Polish "cannot read the answer" notice
        ui_steps.fake_readiness(page, HTTPStatus.OK, UNREADABLE_BODY)
        app = ui_steps.open_application(page)
        expect(app.notice_text).to_have_text(ShellMessages.INVALID)

    def test_a_recheck_clears_the_notice_once_the_database_is_back(self, page: Page):
        # 1. Open the shell while the readiness probe reports the database unavailable
        # 2. Let the probe reach the real backend again and re-check from the notice
        # 3. Verification: the notice disappears
        ui_steps.fake_readiness(page, HTTPStatus.SERVICE_UNAVAILABLE, UNAVAILABLE_BODY)
        app = ui_steps.open_application(page)
        expect(app.notice_text).to_have_text(ShellMessages.UNAVAILABLE)
        ui_steps.restore_readiness(page)
        ui_steps.trigger_recheck(app)
        expect(app.connection_notice).to_be_hidden()

    def test_the_skip_link_moves_focus_to_the_content(self, page: Page):
        # 1. Open the application shell
        # 2. Press Tab: the first stop is the "Przejdź do treści" skip link
        # 3. Press Enter on it
        # 4. Verification: the main content has the keyboard focus
        app = ui_steps.open_application(page)
        page.keyboard.press("Tab")
        expect(app.skip_link).to_be_focused()
        page.keyboard.press("Enter")
        expect(app.content).to_be_focused()
