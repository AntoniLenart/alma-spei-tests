"""Reusable, named test steps.

The ``@step`` decorator (see ``_decorator.py``) wraps a plain function so that
calling it is logged and recorded as an Allure step. Group related steps into
``*_steps.py`` modules here and call them from tests; this keeps step logic DRY
and gives every test a readable, numbered scenario in the Allure report.

Convention inside a test body: one numbered comment per scenario step, with the
final numbered comment being the verification, e.g.::

    def test_ready_probe_reports_ok(self, api):
        # 1. Request the readiness probe
        response = health_steps.request_readiness(api)
        # 2. Verification: HTTP 200 and status "ok"
        assert_that(response.status_code).described_as("ready HTTP status").is_equal_to(200)
"""

from alma_spei_tests.steps._decorator import step

__all__ = ["step"]
