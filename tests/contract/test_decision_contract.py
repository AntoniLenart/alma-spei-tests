"""Contract tests: review decision, proposal and preview responses vs contracts/decisions.cljc
(task 38)."""

from typing import Any

import allure
from assertpy import soft_assertions

from alma_spei_tests.assertions import assert_matches_contract
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.contracts import (
    BLOCKERS_RESPONSE,
    DECISION_RESPONSE,
    EVENTS_RESPONSE,
    ITEMS_RESPONSE,
    PAYMENTS_RESPONSE,
    PREVIEW_RESPONSE,
    PROPOSAL_RESPONSE,
    PROPOSALS_RESPONSE,
    RECONCILIATION_RESPONSE,
)
from alma_spei_tests.data import existing_donor, new_donor_profile
from alma_spei_tests.steps import review_steps
from alma_spei_tests.testbase import BaseContractTest


@allure.feature("Review decision contract")
class TestDecisionContract(BaseContractTest):
    def test_empty_decision_response_matches_contract(self, api: AlmaSpeiApi, staged_batch_id: str):
        # 1. Read an untouched row's decision
        # 2. Verification: the body satisfies decision-response
        body = review_steps.read_decision(api, staged_batch_id, 1).json()
        assert_matches_contract(body, DECISION_RESPONSE, "decision-response")

    def test_saved_decision_response_matches_contract(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Save a complete decision
        # 2. Verification: the body satisfies decision-response
        body = review_steps.save_decision(api, staged_batch_id, 1, existing_donor(donor)).json()
        assert_matches_contract(body, DECISION_RESPONSE, "decision-response")

    def test_proposal_responses_match_contract(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Propose a donor, then list the batch's proposals
        # 2. Verification: proposal-response and proposals-response
        created = review_steps.propose_donor(
            api, staged_batch_id, new_donor_profile(tag=tag).to_payload()
        ).json()
        listed = review_steps.list_proposals(api, staged_batch_id).json()
        with soft_assertions():
            assert_matches_contract(created, PROPOSAL_RESPONSE, "proposal-response")
            assert_matches_contract(listed, PROPOSALS_RESPONSE, "proposals-response")

    def test_payments_response_matches_contract(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Look up a donor's existing payments
        # 2. Verification: the body satisfies payments-response
        body = review_steps.lookup_payments(
            api, staged_batch_id, [("donor-id", donor["id"])]
        ).json()
        assert_matches_contract(body, PAYMENTS_RESPONSE, "payments-response")

    def test_blockers_response_matches_contract(self, api: AlmaSpeiApi, staged_batch_id: str):
        # 1. Read the blockers of an undecided batch
        # 2. Verification: the body satisfies blockers-response
        body = review_steps.read_blockers(api, staged_batch_id).json()
        assert_matches_contract(body, BLOCKERS_RESPONSE, "blockers-response")


@allure.feature("Review decision contract")
class TestPreviewContract(BaseContractTest):
    def test_preview_responses_match_contract(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Prepare a preview of a decided batch, read it back and read its items
        # 2. Verification: preview-response (created and read) and items-response
        batch_id = decided_upload["batch"]["id"]
        created = review_steps.create_preview(api, batch_id)
        preview_id = created["preview"]["id"]
        read = review_steps.read_preview(api, batch_id, preview_id).json()
        items = review_steps.read_preview_items(api, batch_id, preview_id).json()
        with soft_assertions():
            assert_matches_contract(created, PREVIEW_RESPONSE, "preview-response")
            assert_matches_contract(read, PREVIEW_RESPONSE, "preview-response")
            assert_matches_contract(items, ITEMS_RESPONSE, "items-response")

    def test_events_response_matches_contract(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Read the review history of a decided batch
        # 2. Verification: the body satisfies events-response
        body = review_steps.read_review_events(api, decided_upload["batch"]["id"]).json()
        assert_matches_contract(body, EVENTS_RESPONSE, "events-response")


@allure.feature("Review decision contract")
class TestReconciliationContract(BaseContractTest):
    def test_reconciliation_responses_match_contract(self, api: AlmaSpeiApi, staged_batch_id: str):
        # 1. Reconcile a staged batch, then read its report
        # 2. Verification: both bodies satisfy the reconciliation response
        posted = review_steps.reconcile(api, staged_batch_id, review_steps.policy()).json()
        read = review_steps.read_reconciliation(api, staged_batch_id).json()
        with soft_assertions():
            assert_matches_contract(posted, RECONCILIATION_RESPONSE, "reconciliation (POST)")
            assert_matches_contract(read, RECONCILIATION_RESPONSE, "reconciliation (GET)")
