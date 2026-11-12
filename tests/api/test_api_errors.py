"""API tests for cross-cutting error handling: unknown routes."""

import allure

from alma_spei_tests.assertions import assert_not_found, assert_security_headers
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.steps import health_steps
from alma_spei_tests.testbase import BaseApiTest


@allure.feature("API errors")
class TestApiErrors(BaseApiTest):
    def test_unknown_api_route_returns_polish_not_found(self, anonymous_api: AlmaSpeiApi):
        # 1. Request a route that does not exist under /api/
        # 2. Verification: HTTP 404 with the Polish JSON not-found payload and security headers
        response = health_steps.request_unknown_api_route(anonymous_api)
        assert_not_found(response)
        assert_security_headers(response)
