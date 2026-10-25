"""Disruptive E2E test: the shell recovers after a backend restart.

This restarts the backend process mid-test, so it is marked ``@disruptive``:
deselected unless ``--run-disruptive`` (or ``--group disruptive``) is passed, and
isolated onto a single xdist worker so it cannot interfere with other tests that
share the running stack.
"""

import allure
from assertpy import assert_that

from alma_spei_tests.markers import disruptive
from alma_spei_tests.orchestration import Stack
from alma_spei_tests.pages.app_page import AppPage, ShellMessages
from alma_spei_tests.testbase import BaseE2ETest


@disruptive
@allure.feature("Resilience")
class TestBackendRestart(BaseE2ETest):
    def test_shell_recovers_after_backend_restart(self, app_page: AppPage, stack: Stack):
        # 1. Open the shell and confirm it starts ready
        # 2. Restart the backend process (disruptive action)
        # 3. Re-open the shell and wait for recovery
        # 4. Verification: the shell is ready again after the restart
        app_page.open()
        app_page.wait_for_status(ShellMessages.OK)
        stack.restart_backend()
        app_page.open()
        app_page.wait_for_status(ShellMessages.OK)
        assert_that(app_page.status_text()).described_as(
            "the shell should recover to ready after a backend restart"
        ).is_equal_to(ShellMessages.OK)
