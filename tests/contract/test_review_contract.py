"""Contract tests: review responses vs contracts/review.cljc (task 37)."""

from typing import Any

import allure

from alma_spei_tests.assertions import assert_matches_contract
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.contracts import BATCH_RESPONSE, COMPARISON_RESPONSE, QUEUE_RESPONSE
from alma_spei_tests.steps import imports_steps
from alma_spei_tests.testbase import BaseContractTest


@allure.feature("Review contract")
class TestReviewContract(BaseContractTest):
    def test_queue_response_matches_contract(self, api: AlmaSpeiApi, staged_upload: dict[str, Any]):
        # 1. Read the review queue with a staged batch in it
        # 2. Verification: the body satisfies queue-response
        body = imports_steps.review_queue(api).json()
        assert_matches_contract(body, QUEUE_RESPONSE, "queue-response")

    def test_batch_response_matches_contract(self, api: AlmaSpeiApi, staged_upload: dict[str, Any]):
        # 1. Read a staged batch by id
        # 2. Verification: the body satisfies batch-response
        body = imports_steps.read_batch(api, staged_upload["batch"]["id"]).json()
        assert_matches_contract(body, BATCH_RESPONSE, "batch-response")

    def test_comparison_response_matches_contract(
        self, api: AlmaSpeiApi, staged_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Compare a staged row with a donor
        # 2. Verification: the body satisfies comparison-response
        body = imports_steps.compare(api, staged_upload["batch"]["id"], 1, 1, donor["id"]).json()
        assert_matches_contract(body, COMPARISON_RESPONSE, "comparison-response")
