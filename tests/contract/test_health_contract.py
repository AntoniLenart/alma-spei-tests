"""Contract tests: health responses must conform to the shared Malli schema.

The Python mirror of the contract lives in ``alma_spei_tests.contracts.health``.
If a response drifts from the closed ``{:status (enum "ok" "unavailable")}``
shape, these tests fail.
"""

import allure

from alma_spei_tests.assertions import assert_matches_contract, assert_valid_health_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.contracts import HEALTH_RESPONSE
from alma_spei_tests.steps import health_steps
from alma_spei_tests.testbase import BaseContractTest


@allure.feature("Health contract")
class TestHealthResponseContract(BaseContractTest):
    def test_liveness_body_matches_health_contract(self, anonymous_api: AlmaSpeiApi):
        # 1. Request the liveness probe
        # 2. Verification: the body satisfies the shared health contract
        body = health_steps.request_liveness(anonymous_api).json()
        assert_matches_contract(body, HEALTH_RESPONSE, "health")

    def test_readiness_body_matches_health_contract(self, anonymous_api: AlmaSpeiApi):
        # 1. Request the readiness probe
        # 2. Verification: the body satisfies the shared health contract
        body = health_steps.request_readiness(anonymous_api).json()
        assert_matches_contract(body, HEALTH_RESPONSE, "health")

    def test_readiness_status_is_in_allowed_enum(self, anonymous_api: AlmaSpeiApi):
        # 1. Request the readiness probe and read the status field
        # 2. Verification: the status is a valid health status value
        status = health_steps.request_readiness(anonymous_api).json().get("status")
        assert_valid_health_status(status)
