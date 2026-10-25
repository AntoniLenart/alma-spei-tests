"""API tests for error handling on unknown routes.

The backend returns a JSON 404 with a Polish message for unknown ``/api/*``
routes (see src/api/alma_spei/api/http/routes.clj).
"""

import allure

from alma_spei_tests.api import ApiClient
from alma_spei_tests.assertions import assert_not_found
from alma_spei_tests.steps import health_steps
from alma_spei_tests.testbase import BaseApiTest


@allure.feature("API errors")
class TestUnknownApiRoute(BaseApiTest):
    def test_unknown_api_route_returns_json_404(self, api: ApiClient):
        # 1. Request a route under /api/ that does not exist
        # 2. Verification: 404, JSON content type and the Polish not-found payload
        response = health_steps.request_unknown_api_route(api, "/api/nope")
        assert_not_found(response)
