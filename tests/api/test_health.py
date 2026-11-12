"""API tests for the health endpoints (no authentication required)."""

import allure
import pytest

from alma_spei_tests.assertions import (
    assert_health_ok,
    assert_json_content_type,
    assert_security_headers,
)
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.steps import health_steps
from alma_spei_tests.testbase import BaseApiTest


@allure.feature("Health")
class TestHealthProbes(BaseApiTest):
    @pytest.mark.smoke
    def test_liveness_probe_reports_ok(self, anonymous_api: AlmaSpeiApi):
        # 1. Request the liveness probe without signing in
        # 2. Verification: HTTP 200 and body {"status": "ok"}
        response = health_steps.request_liveness(anonymous_api)
        assert_health_ok(response)

    @pytest.mark.smoke
    def test_readiness_probe_reports_ok_when_db_is_up(self, anonymous_api: AlmaSpeiApi):
        # 1. Request the readiness probe (the orchestrated stack has the DB up)
        # 2. Verification: HTTP 200 and body {"status": "ok"}
        response = health_steps.request_readiness(anonymous_api)
        assert_health_ok(response)

    def test_readiness_is_served_as_json_with_security_headers(self, anonymous_api: AlmaSpeiApi):
        # 1. Request the readiness probe
        # 2. Verification: JSON content type plus no-store / nosniff / no-referrer headers
        response = health_steps.request_readiness(anonymous_api)
        assert_json_content_type(response)
        assert_security_headers(response)
