"""API tests for saved review decisions and donor proposals (task 38).

A decision is explicit and versioned: it links a parser-valid row to an active
donor or to a donor proposal of the same batch, with a reviewer-asserted
currency, evidence and payment treatment. Every write checks the batch and
decision versions the reviewer saw, so a stale write never overwrites another.
"""

import uuid
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_error_includes, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import (
    EVIDENCE_MAX_LENGTH,
    STAGED_BATCH_VERSION,
    ApiErrorPayload,
    DecisionKind,
    Disposition,
    Header,
    ImportErrorPayload,
    ReviewErrorPayload,
)
from alma_spei_tests.data import (
    UNDECIDED_PAYMENT,
    UNRESOLVED,
    BankRow,
    BankStatement,
    DonorFactory,
    Financial,
    ReviewVersions,
    existing_donor,
    new_donor_profile,
    proposal_payload,
    proposed_donor,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, donors_steps, imports_steps, review_steps
from alma_spei_tests.testbase import BaseApiTest

#: An impossible date: the row is staged as invalid.
INVALID_DATE = "2026-02-30"
SOME_AMOUNT = "5,00"


@allure.feature("Review decisions")
class TestSavingDecisions(BaseApiTest):
    @pytest.mark.smoke
    def test_linking_a_row_to_a_donor_saves_an_attributed_complete_decision(
        self,
        api: AlmaSpeiApi,
        staged_batch_id: str,
        donor: dict[str, Any],
        admin_id: str,
        settings: Settings,
    ):
        # 1. Link row 1 of a staged batch to an existing donor as a new PLN payment
        # 2. Verification: 200; version 1, complete, attributed to the reviewer, labelled with
        #    the donor; the batch counts one complete row and moved on one version
        response = review_steps.save_decision(api, staged_batch_id, 1, existing_donor(donor))
        body = response.json()
        decision = body["decision"]
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "saving a decision")
            assert_that((decision["version"], decision["kind"], decision["complete"])).described_as(
                "the first save should be a complete version 1"
            ).is_equal_to((1, DecisionKind.EXISTING_DONOR, True))
            assert_that(
                (decision["reviewer-id"], decision["reviewer-name"], decision["target-label"])
            ).described_as("the decision should name its reviewer and target").is_equal_to(
                (admin_id, settings.admin_display_name, donor["name"])
            )
            assert_that((body["batch"]["reviewed-rows"], body["batch"]["version"])).described_as(
                "the batch should count the row and advance"
            ).is_equal_to((1, STAGED_BATCH_VERSION + 1))

    def test_identity_without_a_payment_review_is_saved_but_incomplete(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Link row 1 to a donor, leaving currency and payment treatment open
        # 2. Verification: saved as incomplete; the batch counts no complete row
        decision = existing_donor(donor, UNDECIDED_PAYMENT)
        body = review_steps.decide(api, staged_batch_id, 1, decision)
        assert_that((body["decision"]["complete"], body["batch"]["reviewed-rows"])).described_as(
            "an open payment review should leave the row incomplete"
        ).is_equal_to((False, 0))

    def test_clearing_a_decision_keeps_a_new_unresolved_version(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Save a complete decision for row 1
        # 2. Leave the row unresolved
        # 3. Verification: version 2, unresolved, no target; the batch counts no row
        review_steps.decide(api, staged_batch_id, 1, existing_donor(donor))
        body = review_steps.decide(api, staged_batch_id, 1, UNRESOLVED)
        decision = body["decision"]
        assert_that(
            (
                decision["version"],
                decision["kind"],
                decision["donor-id"],
                body["batch"]["reviewed-rows"],
            )
        ).described_as("clearing should be a recorded unresolved version").is_equal_to(
            (2, DecisionKind.UNRESOLVED, None, 0)
        )

    def test_repeating_the_saved_decision_changes_nothing(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Save a decision for row 1
        # 2. Save exactly the same decision again against the current versions
        # 3. Verification: same decision version and batch version (a no-op)
        first = review_steps.decide(api, staged_batch_id, 1, existing_donor(donor))
        again = review_steps.decide(api, staged_batch_id, 1, existing_donor(donor))
        assert_that((again["decision"]["version"], again["batch"]["version"])).described_as(
            "an identical save should not create a new version"
        ).is_equal_to((first["decision"]["version"], first["batch"]["version"]))

    def test_unsaved_row_has_no_decision(self, api: AlmaSpeiApi, staged_batch_id: str):
        # 1. Read the decision of an untouched row
        # 2. Verification: 200 with no decision yet
        response = review_steps.read_decision(api, staged_batch_id, 2)
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "reading an untouched row")
            assert_that(response.json()["decision"]).described_as(
                "an untouched row should have no decision"
            ).is_none()


@allure.feature("Review decisions")
class TestDecisionGuards(BaseApiTest):
    def test_a_stale_decision_version_is_refused(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Save a decision for row 1 (now version 1)
        # 2. Save another decision claiming the row was still undecided (version 0)
        # 3. Verification: 409 stale-review and the saved decision is unchanged
        review_steps.decide(api, staged_batch_id, 1, existing_donor(donor))
        versions = review_steps.read_versions(api, staged_batch_id, 1)
        stale = ReviewVersions(versions.batch_version, 0, versions.catalog_version)
        response = review_steps.submit_decision(
            api, staged_batch_id, 1, UNRESOLVED.to_payload(stale)
        )
        current = review_steps.read_decision(api, staged_batch_id, 1).json()["decision"]
        with soft_assertions():
            assert_error(response, HTTPStatus.CONFLICT, ReviewErrorPayload.STALE_REVIEW)
            assert_that((current["version"], current["kind"])).described_as(
                "the refused write should not change the saved decision"
            ).is_equal_to((1, DecisionKind.EXISTING_DONOR))

    def test_a_stale_batch_version_is_refused(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Save a decision for row 1 (the batch moves on)
        # 2. Save row 2 against the batch version read before that save
        # 3. Verification: 409 stale-import
        before = review_steps.read_versions(api, staged_batch_id, 2)
        review_steps.decide(api, staged_batch_id, 1, existing_donor(donor))
        payload = existing_donor(donor).to_payload(before)
        response = review_steps.submit_decision(api, staged_batch_id, 2, payload)
        assert_error(response, HTTPStatus.CONFLICT, ImportErrorPayload.STALE_IMPORT)

    def test_an_outdated_donor_version_is_refused(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Link row 1 to a donor while claiming an older donor version than the current one
        # 2. Verification: 409 stale-review
        outdated = existing_donor(donor).with_changes(target_version=donor["version"] + 1)
        response = review_steps.save_decision(api, staged_batch_id, 1, outdated)
        assert_error(response, HTTPStatus.CONFLICT, ReviewErrorPayload.STALE_REVIEW)

    def test_an_archived_donor_cannot_receive_the_payment(
        self,
        api: AlmaSpeiApi,
        db: DbQueries,
        staged_batch_id: str,
        donor_factory: DonorFactory,
        tag: str,
    ):
        # 1. Create a tagged donor and archive it
        # 2. Link row 1 to the archived donor
        # 3. Verification: 409 inactive-donor
        archived = donor_factory(new_donor_profile(tag=tag))
        db_steps.archive_donor(db, archived["id"])
        response = review_steps.save_decision(api, staged_batch_id, 1, existing_donor(archived))
        assert_error(response, HTTPStatus.CONFLICT, ReviewErrorPayload.INACTIVE_DONOR)

    def test_an_unknown_donor_is_not_found(self, api: AlmaSpeiApi, staged_batch_id: str):
        # 1. Link row 1 to a donor id that does not exist
        # 2. Verification: 404 donor not-found
        ghost = {"id": str(uuid.uuid4()), "version": 1}
        response = review_steps.save_decision(api, staged_batch_id, 1, existing_donor(ghost))
        assert_error(response, HTTPStatus.NOT_FOUND, ApiErrorPayload.DONOR_NOT_FOUND)

    def test_an_invalid_row_cannot_be_decided(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage a statement whose only line has an impossible date
        # 2. Link that row to a donor
        # 3. Verification: 409 invalid-row - the source must be corrected instead
        statement = BankStatement([BankRow(INVALID_DATE, donor["name"], tag, SOME_AMOUNT)])
        batch = imports_steps.upload_staged(api, f"{tag}.csv", statement.to_csv())["batch"]
        response = review_steps.save_decision(api, batch["id"], 1, existing_donor(donor))
        assert_error(response, HTTPStatus.CONFLICT, ReviewErrorPayload.INVALID_ROW)

    @pytest.mark.parametrize(
        "financial",
        [
            pytest.param(Financial(currency="pln"), id="lower-case-currency"),
            pytest.param(Financial(currency="PLNX"), id="four-letter-currency"),
            pytest.param(
                Financial(evidence="x" * (EVIDENCE_MAX_LENGTH + 1)), id="evidence-too-long"
            ),
        ],
    )
    def test_malformed_payment_review_is_rejected(
        self,
        api: AlmaSpeiApi,
        staged_batch_id: str,
        donor: dict[str, Any],
        financial: Financial,
    ):
        # 1. Save a decision with a malformed currency or an over-long evidence note
        # 2. Verification: 400 import validation
        response = review_steps.save_decision(
            api, staged_batch_id, 1, existing_donor(donor, financial)
        )
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    def test_client_supplied_review_fields_are_rejected(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any], admin_id: str
    ):
        # 1. Save a decision that also names its reviewer
        # 2. Verification: 400 import validation - the server attributes decisions itself
        versions = review_steps.read_versions(api, staged_batch_id, 1)
        payload = {**existing_donor(donor).to_payload(versions), "reviewer-id": admin_id}
        response = review_steps.submit_decision(api, staged_batch_id, 1, payload)
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    def test_a_duplicate_reference_needs_a_payment(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Mark row 1 as already recorded without naming the existing payment
        # 2. Verification: 400 import validation
        claimed = existing_donor(donor, Financial().with_changes(disposition=Disposition.EXISTING))
        response = review_steps.save_decision(api, staged_batch_id, 1, claimed)
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    def test_a_missing_csrf_header_is_refused(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Save a decision without the X-CSRF-Token header
        # 2. Verification: 403 csrf
        payload = existing_donor(donor).to_payload(
            review_steps.read_versions(api, staged_batch_id, 1)
        )
        response = review_steps.submit_decision(
            api, staged_batch_id, 1, payload, headers={Header.CSRF_TOKEN: None}
        )
        assert_error(response, HTTPStatus.FORBIDDEN, ReviewErrorPayload.CSRF)

    def test_anonymous_client_cannot_read_a_decision(
        self, anonymous_api: AlmaSpeiApi, staged_batch_id: str
    ):
        # 1. Read a row decision without signing in
        # 2. Verification: 401 unauthenticated
        response = review_steps.read_decision(anonymous_api, staged_batch_id, 1)
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)


@allure.feature("Review decisions")
class TestDonorProposals(BaseApiTest):
    def test_a_proposal_is_versioned_and_creates_no_donor(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Propose a new donor for a staged batch
        # 2. Verification: 201 with version 1 and the typed profile; nobody by that name exists
        profile = new_donor_profile(tag=tag)
        response = review_steps.propose_donor(api, staged_batch_id, profile.to_payload())
        proposal = response.json()["proposal"]
        found = donors_steps.list_tagged(api, tag, status="all")
        with soft_assertions():
            assert_status(response, HTTPStatus.CREATED, "proposing a donor")
            assert_that((proposal["version"], proposal["profile"]["name"])).described_as(
                "the proposal should be version 1 with the typed name"
            ).is_equal_to((1, profile.name))
            assert_that(found).described_as(
                "a proposal should not create a canonical donor"
            ).is_empty()

    def test_a_proposal_requires_both_explicit_checks(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Propose a donor without confirming that existing profiles were checked
        # 2. Verification: 400 import validation
        versions = review_steps.read_versions(api, staged_batch_id, 1)
        payload = proposal_payload(
            new_donor_profile(tag=tag).to_payload(),
            versions.batch_version,
            versions.catalog_version,
        )
        response = review_steps.submit_proposal(
            api, staged_batch_id, {**payload, "checked-existing": False}
        )
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    def test_a_proposal_without_a_city_is_rejected(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Propose a donor with a blank city
        # 2. Verification: 400 import validation
        profile = new_donor_profile(tag=tag).with_changes(city=" ")
        response = review_steps.propose_donor(api, staged_batch_id, profile.to_payload())
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    def test_one_proposal_can_receive_several_rows(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Propose one donor and link both rows to it
        # 2. Verification: both decisions are complete and point at the same proposal
        proposal = review_steps.create_proposal(
            api, staged_batch_id, new_donor_profile(tag=tag).to_payload()
        )
        review_steps.decide_rows(
            api, staged_batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        decisions = [
            review_steps.read_decision(api, staged_batch_id, row).json()["decision"]
            for row in (1, 2)
        ]
        assert_that([(d["proposal-id"], d["complete"]) for d in decisions]).described_as(
            "both rows should reuse the one proposal"
        ).is_equal_to([(proposal["id"], True)] * 2)

    def test_editing_a_proposal_needs_its_current_version(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Propose a donor, then edit it once (now version 2)
        # 2. Edit it again claiming version 1
        # 3. Verification: the first edit returns version 2; the second is 409 stale-review
        profile = new_donor_profile(tag=tag)
        proposal = review_steps.create_proposal(api, staged_batch_id, profile.to_payload())
        renamed = profile.with_changes(name=f"{profile.name} (popr.)").to_payload()
        first = review_steps.update_proposal(
            api, staged_batch_id, proposal["id"], edit_payload(api, staged_batch_id, renamed, 1)
        )
        second = review_steps.update_proposal(
            api,
            staged_batch_id,
            proposal["id"],
            edit_payload(api, staged_batch_id, profile.to_payload(), 1),
        )
        with soft_assertions():
            assert_that(first.json()["proposal"]["version"]).described_as(
                "an effective edit should create version 2"
            ).is_equal_to(2)
            assert_error(second, HTTPStatus.CONFLICT, ReviewErrorPayload.STALE_REVIEW)

    def test_proposals_cannot_cross_batches(self, api: AlmaSpeiApi, staged_batch_id: str, tag: str):
        # 1. Propose a donor for one staged batch
        # 2. Stage a second batch and link its row 1 to that proposal
        # 3. Verification: 404 proposal not-found
        proposal = review_steps.create_proposal(
            api, staged_batch_id, new_donor_profile(tag=tag).to_payload()
        )
        other = imports_steps.upload_staged(
            api,
            f"{tag}-b.csv",
            BankStatement([BankRow("2026-03-01", "X", tag, SOME_AMOUNT)]).to_csv(),
        )["batch"]
        response = review_steps.save_decision(api, other["id"], 1, proposed_donor(proposal))
        assert_error(response, HTTPStatus.NOT_FOUND, ReviewErrorPayload.PROPOSAL_NOT_FOUND)

    def test_proposals_are_listed_for_their_batch(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Propose two donors
        # 2. List the batch's proposals
        # 3. Verification: both, oldest first
        names = [f"Fundacja Pierwsza {tag}", f"Fundacja Druga {tag}"]
        for name in names:
            profile = new_donor_profile(tag=tag).with_changes(name=name)
            review_steps.create_proposal(api, staged_batch_id, profile.to_payload())
        body = review_steps.list_proposals(api, staged_batch_id).json()
        assert_that([p["profile"]["name"] for p in body["proposals"]]).described_as(
            "the batch's proposals should be listed oldest first"
        ).is_equal_to(names)


@allure.feature("Review decisions")
class TestPaymentLookup(BaseApiTest):
    def test_a_donor_without_payments_has_none_to_reference(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Look up existing payments of a new donor
        # 2. Verification: 200, no payments
        response = review_steps.lookup_payments(api, staged_batch_id, [("donor-id", donor["id"])])
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "looking up a donor's payments")
            assert_that((response.json()["payments"], response.json()["total"])).described_as(
                "a new donor should have no payments"
            ).is_equal_to(([], 0))

    def test_payment_lookup_needs_an_explicit_donor(self, api: AlmaSpeiApi, staged_batch_id: str):
        # 1. Look up payments without naming a donor
        # 2. Verification: 400 import validation (no browsing of all payments)
        response = review_steps.lookup_payments(api, staged_batch_id, [])
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)


# --- file-local helpers -------------------------------------------------------
def edit_payload(
    api: AlmaSpeiApi, batch_id: str, profile: Mapping[str, object], version: int
) -> dict[str, object]:
    """PUT body for a proposal edit against the current batch version."""
    batch_version = review_steps.read_versions(api, batch_id, 1).batch_version
    return {"batch-version": batch_version, "version": version, "profile": profile}
