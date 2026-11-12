"""API tests for cross-cutting error handling: unknown routes and bad bodies."""

from http import HTTPStatus

import allure

from alma_spei_tests.assertions import assert_error, assert_not_found, assert_security_headers
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import BODY_LIMIT_BYTES, ApiErrorPayload
from alma_spei_tests.steps import auth_steps, donors_steps, health_steps
from alma_spei_tests.testbase import BaseApiTest

#: Not valid JSON - the request decoder must reject it.
MALFORMED_JSON = b"{invalid-json"


@allure.feature("API errors")
class TestApiErrors(BaseApiTest):
    def test_unknown_api_route_returns_polish_not_found(self, anonymous_api: AlmaSpeiApi):
        # 1. Request a route that does not exist under /api/
        # 2. Verification: HTTP 404 with the Polish JSON not-found payload and security headers
        response = health_steps.request_unknown_api_route(anonymous_api)
        assert_not_found(response)
        assert_security_headers(response)

    def test_malformed_json_body_is_rejected(self, api: AlmaSpeiApi):
        # 1. POST a syntactically invalid JSON body to the donor endpoint
        # 2. Verification: HTTP 400 with the malformed-body payload
        response = donors_steps.request_create_with_content(api, MALFORMED_JSON)
        assert_error(response, HTTPStatus.BAD_REQUEST, ApiErrorPayload.MALFORMED_BODY)

    def test_oversized_body_is_rejected_before_processing(self, anonymous_api: AlmaSpeiApi):
        # 1. Build a login body larger than the 16 KiB form limit
        # 2. Submit it
        # 3. Verification: HTTP 413 with the body-too-large payload
        body = {"username": "x" * (BODY_LIMIT_BYTES + 1), "password": "x"}
        response = auth_steps.login_with(anonymous_api, body)
        assert_error(response, HTTPStatus.REQUEST_ENTITY_TOO_LARGE, ApiErrorPayload.BODY_TOO_LARGE)
