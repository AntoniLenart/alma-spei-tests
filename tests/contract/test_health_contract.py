"""Contract tests: health responses must conform to the shared Malli schema.

The Python mirror of the contract lives in
``alma_spei_tests.contracts.health``. If the backend's response drifts from the
closed ``{:status (enum "ok" "unavailable")}`` shape, these tests fail.
"""

import allure

from alma_spei_tests.api import ApiClient
from alma_spei_tests.assertions import assert_matches_health_contract, assert_valid_health_status
from alma_spei_tests.steps import health_steps
from alma_spei_tests.testbase import BaseContractTest


@allure.feature("Health contract")
class TestHealthResponseContract(BaseContractTest):
    def test_liveness_body_matches_health_contract(self, api: ApiClient):
        # 1. Request the liveness probe
        # 2. Verification: the body satisfies the shared health contract
        body = health_steps.request_liveness(api).json()
        assert_matches_health_contract(body)

    def test_readiness_body_matches_health_contract(self, api: ApiClient):
        # 1. Request the readiness probe
        # 2. Verification: the body satisfies the shared health contract
        body = health_steps.request_readiness(api).json()
        assert_matches_health_contract(body)

    def test_readiness_status_is_in_allowed_enum(self, api: ApiClient):
        # 1. Request the readiness probe and read the status field
        # 2. Verification: the status is a valid health status value
        status = health_steps.request_readiness(api).json().get("status")
        assert_valid_health_status(status)
