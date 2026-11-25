"""API tests for the two views of the reconciliation report (task 62).

``GET /api/imports/:id/reconciliation`` takes ``queue=exceptions`` (the default)
or ``queue=exact``. The exceptions view pages the rows left for a person; the
exact view pages, read-only, the rows the matching linked to a donor by itself,
each with that donor. Manual decisions and new donor proposals are never listed
as exact matches. Both views report the exact-match count of the current
catalogue snapshot.
"""

from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error_includes
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import EntityType, ImportErrorPayload, ReconciliationQueue
from alma_spei_tests.data import (
    DonorFactory,
    existing_donor,
    new_donor_profile,
    sender_of,
    sender_with_address,
)
from alma_spei_tests.steps import imports_steps, review_steps
from alma_spei_tests.testbase import BaseApiTest

INDIVIDUALS = review_steps.policy(new_donor_type=EntityType.INDIVIDUAL)


@allure.feature("Reconciliation views")
class TestReconciliationQueues(BaseApiTest):
    def test_the_default_view_lists_only_the_exceptions(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage an exact match (row 1) and a sender without an address (row 2); reconcile
        # 2. Read the report without choosing a view
        # 3. Verification: the exceptions view with row 2 only, and the exact match counted
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(donor), donor["name"]])
        review_steps.reconcile(api, batch_id, INDIVIDUALS)
        body = review_steps.read_reconciliation(api, batch_id).json()
        assert_that(view_of(body)).described_as(
            "the default view should list only the rows left for a person"
        ).is_equal_to((ReconciliationQueue.EXCEPTIONS, [2], [], 1))

    def test_the_exact_view_lists_the_automatic_matches_with_their_donors(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage an exact match (row 1) and a sender without an address (row 2); reconcile
        # 2. Read the exact view
        # 3. Verification: row 1 with its donor, and no exceptions in this view
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(donor), donor["name"]])
        review_steps.reconcile(api, batch_id, INDIVIDUALS)
        body = review_steps.read_reconciliation(
            api, batch_id, queue=ReconciliationQueue.EXACT
        ).json()
        with soft_assertions():
            assert_that(view_of(body)).described_as(
                "the exact view should list only the automatic match"
            ).is_equal_to((ReconciliationQueue.EXACT, [], [1], 1))
            assert_that([m["donor"]["id"] for m in body["exact-matches"]]).described_as(
                "the exact match should name its donor"
            ).is_equal_to([donor["id"]])

    def test_a_manual_decision_is_not_an_exact_match(
        self, api: AlmaSpeiApi, donor: dict[str, Any], donor_factory: DonorFactory, tag: str
    ):
        # 1. Stage two exact matches, but link row 2 to its donor by hand first; reconcile
        # 2. Read the exact view
        # 3. Verification: only the automatic row 1 is an exact match
        other = donor_factory(new_donor_profile(tag=tag))
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(donor), sender_of(other)])
        review_steps.decide(api, batch_id, 2, existing_donor(other))
        review_steps.reconcile(api, batch_id, INDIVIDUALS)
        body = review_steps.read_reconciliation(
            api, batch_id, queue=ReconciliationQueue.EXACT
        ).json()
        assert_that(view_of(body)).described_as(
            "a person's decision should not be listed as an automatic match"
        ).is_equal_to((ReconciliationQueue.EXACT, [], [1], 1))

    def test_a_new_donor_proposal_is_not_an_exact_match(self, api: AlmaSpeiApi, tag: str):
        # 1. Stage a sender like nobody and reconcile it with new donors as individuals
        # 2. Read the exact view
        # 3. Verification: the prepared new donor is no exact match, and nothing is left over
        profile = new_donor_profile(tag=tag)
        sender = sender_with_address(
            profile.name, profile.street or "", profile.postal_code or "", profile.city
        )
        batch_id = imports_steps.stage_senders(api, tag, [sender])
        review_steps.reconcile(api, batch_id, INDIVIDUALS)
        body = review_steps.read_reconciliation(
            api, batch_id, queue=ReconciliationQueue.EXACT
        ).json()
        assert_that(view_of(body) + (body["counts"]["new-donors"],)).described_as(
            "a prepared new donor should not count as an exact match"
        ).is_equal_to((ReconciliationQueue.EXACT, [], [], 0, 1))

    @pytest.mark.parametrize("queue", ["everything", ""])
    def test_an_unknown_view_is_refused(
        self, api: AlmaSpeiApi, staged_upload: dict[str, Any], queue: str
    ):
        # 1. Read the report of a staged batch with an unknown view
        # 2. Verification: 400 import validation
        response = review_steps.read_reconciliation(api, staged_upload["batch"]["id"], queue=queue)
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)


# --- file-local helpers -------------------------------------------------------
def view_of(body: dict[str, Any]) -> tuple[str, list[int], list[int], int]:
    """The view, its exception rows, its exact-match rows and the exact-match count."""
    return (
        body["queue"],
        [e["row"]["row-number"] for e in body["exceptions"]],
        [m["row"]["row-number"] for m in body["exact-matches"]],
        body["exact-match-count"],
    )
