"""API tests for the health endpoints.

The layer marker (``api``) is applied automatically by the root conftest because
this file lives under tests/api/. ``smoke`` is added explicitly where relevant.
"""

import allure
import pytest

from alma_spei_tests.api import ApiClient
from alma_spei_tests.assertions import assert_health_ok, assert_json_content_type
from alma_spei_tests.steps import health_steps
from alma_spei_tests.testbase import BaseApiTest


@allure.feature("Health")
class TestHealthLiveness(BaseApiTest):
    @pytest.mark.smoke
    def test_liveness_probe_reports_ok(self, api: ApiClient):
        # 1. Request the liveness probe
        # 2. Verification: HTTP 200 and body {"status": "ok"}
        response = health_steps.request_liveness(api)
        assert_health_ok(response)


@allure.feature("Health")
class TestHealthReadiness(BaseApiTest):
    @pytest.mark.smoke
    def test_readiness_probe_reports_ok_when_db_is_up(self, api: ApiClient):
        # 1. Request the readiness probe (the orchestrated stack has the DB up)
        # 2. Verification: HTTP 200 and body {"status": "ok"}
        response = health_steps.request_readiness(api)
        assert_health_ok(response)

    def test_readiness_content_type_is_json(self, api: ApiClient):
        # 1. Request the readiness probe
        # 2. Verification: the response is served as JSON
        response = health_steps.request_readiness(api)
        assert_json_content_type(response)
