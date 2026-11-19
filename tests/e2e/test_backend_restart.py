"""Disruptive E2E test: the shell recovers after a backend restart.

This restarts the backend process mid-test, so it is marked ``@disruptive``:
deselected unless ``--run-disruptive`` (or ``--group disruptive``) is passed, and
isolated onto a single xdist group so it cannot interleave with other tests.
"""

import allure
from playwright.sync_api import Page, expect

from alma_spei_tests.markers import disruptive
from alma_spei_tests.orchestration import Stack
from alma_spei_tests.steps import ui_steps
from alma_spei_tests.testbase import BaseE2ETest


@disruptive
@allure.feature("Resilience")
class TestBackendRestart(BaseE2ETest):
    def test_shell_recovers_after_backend_restart(self, page: Page, stack: Stack):
        # 1. Open the shell and confirm it starts healthy (no connection notice)
        # 2. Restart the backend process (disruptive action)
        # 3. Re-open the shell and wait for its health check
        # 4. Verification: still no connection notice, and the login form is back
        app = ui_steps.open_application(page)
        expect(app.connection_notice).to_be_hidden()
        stack.restart_backend()
        app = ui_steps.open_application(page)
        expect(app.connection_notice).to_be_hidden()
        ui_steps.open_login(page)
