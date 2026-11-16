"""API tests for applying a reviewed import (task 39).

A commit applies exactly one ready preview, backed by a (synthetic) backup
receipt bound to that preview, in one transaction: new profiles once per
proposal, one payment per new-payment row, explicit references for payments
already in the catalogue. Anything stale - preview, catalogue, receipt - is
refused before a single canonical row is written; an exact repeat returns the
original receipt instead of applying twice.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_error_includes, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    SYNTHETIC_BACKUP_ADAPTER,
    SYNTHETIC_RECEIPT_LIFETIME_S,
    BlockerCode,
    ExecutionErrorPayload,
    Header,
    ImportErrorPayload,
    ImportState,
    ReviewErrorPayload,
)
from alma_spei_tests.data import (
    UNRESOLVED,
    BankRow,
    BankStatement,
    DonorFactory,
    already_recorded,
    existing_donor,
    new_donor_profile,
    proposed_donor,
)
from alma_spei_tests.steps import (
    donors_steps,
    execution_steps,
    imports_steps,
    review_steps,
)
from alma_spei_tests.steps.execution_steps import CommittedImport
from alma_spei_tests.testbase import BaseApiTest


@allure.feature("Import commit")
class TestBackupReceipt(BaseApiTest):
    def test_a_ready_preview_gets_a_labelled_synthetic_receipt(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Prepare a preview of a decided batch
        # 2. Request a backup receipt for it
        # 3. Verification: 200; the receipt is labelled synthetic and stays valid for the
        #    five-minute test lifetime
        preview = review_steps.create_preview(api, decided_upload["batch"]["id"])
        snapshot = preview["preview"]
        response = execution_steps.request_backup(
            api, snapshot["batch-id"], snapshot["id"], execution_steps.backup_payload(preview)
        )
        backup = response.json()["backup"]
        lifetime = datetime.fromisoformat(backup["expires-at"]) - datetime.fromisoformat(
            backup["completed-at"]
        )
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "requesting a backup receipt")
            assert_that((backup["adapter"], backup["synthetic"])).described_as(
                "the receipt should say it is a synthetic test backup"
            ).is_equal_to((SYNTHETIC_BACKUP_ADAPTER, True))
            assert_that(lifetime.total_seconds()).described_as(
                "the synthetic receipt should be valid for five minutes"
            ).is_equal_to(SYNTHETIC_RECEIPT_LIFETIME_S)

    def test_a_receipt_for_a_changed_review_is_refused(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Prepare a preview, then leave row 1 unresolved
        # 2. Request a backup receipt for the old preview at the current batch version
        # 3. Verification: 409 stale-preview
        batch_id = decided_upload["batch"]["id"]
        preview = review_steps.create_preview(api, batch_id)
        review_steps.decide(api, batch_id, 1, UNRESOLVED)
        current = review_steps.read_versions(api, batch_id, 1)
        payload = {
            **execution_steps.backup_payload(preview),
            "batch-version": current.batch_version,
        }
        response = execution_steps.request_backup(api, batch_id, preview["preview"]["id"], payload)
        assert_error(response, HTTPStatus.CONFLICT, ExecutionErrorPayload.STALE_PREVIEW)


@allure.feature("Import commit")
class TestCommit(BaseApiTest):
    @pytest.mark.smoke
    def test_commit_applies_the_previewed_payments(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Prepare, back up and commit a batch decided for one existing donor
        # 2. Read the donor's card
        # 3. Verification: the batch is committed with the preview's summary; the donor now
        #    has both payments, with the staged amounts
        batch_id = decided_upload["batch"]["id"]
        request = execution_steps.approval_request(api, batch_id)
        response = execution_steps.submit_commit(api, request)
        outcome = response.json()
        card = donors_steps.get_donor(api, donor["id"]).json()
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "committing a ready preview")
            assert_that((outcome["batch"]["state"], outcome["commit"]["preview-id"])).described_as(
                "the batch should be committed from that preview"
            ).is_equal_to((ImportState.COMMITTED, request["preview-id"]))
            assert_that(sorted(Decimal(d["amount"]) for d in card["donations"])).described_as(
                "the donor should hold exactly the two staged payments"
            ).is_equal_to(sorted(staged_amounts(api, batch_id)))

    def test_a_shared_proposal_becomes_one_donor_with_both_payments(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Propose one donor, link both rows to it and commit
        # 2. Search donors by the test's tag
        # 3. Verification: exactly one new donor with the typed profile, holding both payments
        profile = new_donor_profile(tag=tag)
        proposal = review_steps.create_proposal(api, staged_batch_id, profile.to_payload())
        review_steps.decide_rows(
            api, staged_batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        execution_steps.commit_import(api, staged_batch_id)
        created = donors_steps.list_tagged(api, tag)
        card = donors_steps.get_donor(api, created[0]["id"]).json() if created else {}
        with soft_assertions():
            assert_that([d["name"] for d in created]).described_as(
                "the proposal should become one donor"
            ).is_equal_to([profile.name])
            assert_that(card.get("donations-total")).described_as(
                "the new donor should hold both payments"
            ).is_equal_to(2)

    def test_identical_rows_stay_separate_payments(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage two lines with the same date, sender and amount (different descriptions)
        # 2. Decide both as new payments for one donor and commit
        # 3. Verification: the donor holds two payments - equal facts never collapse silently
        twin = BankRow("2026-04-01", donor["name"], f"{tag} #1", "50,00")
        statement = BankStatement([twin, BankRow(twin.date, twin.sender, f"{tag} #2", twin.amount)])
        batch = imports_steps.upload_staged(api, f"{tag}.csv", statement.to_csv())["batch"]
        review_steps.decide_rows(api, batch["id"], [existing_donor(donor), existing_donor(donor)])
        execution_steps.commit_import(api, batch["id"])
        card = donors_steps.get_donor(api, donor["id"]).json()
        assert_that(card["donations-total"]).described_as(
            "two genuine identical payments should both be recorded"
        ).is_equal_to(2)

    def test_a_payment_already_recorded_is_referenced_not_added(
        self, api: AlmaSpeiApi, committed_import: CommittedImport, donor: dict[str, Any], tag: str
    ):
        # 1. Commit a batch that gave the donor two payments (fixture)
        # 2. Stage a new file repeating row 1's facts; mark it as that existing payment
        # 3. Prepare a preview and commit it
        # 4. Verification: the preview plans one reference and no payment; the donor still
        #    holds two payments
        batch_id = committed_import.batch_id
        source = imports_steps.read_rows(api, batch_id).json()["rows"][0]["payload"]
        statement = BankStatement(
            [
                BankRow(
                    source["source-date"], donor["name"], f"{tag} powtórka", source["source-amount"]
                )
            ]
        )
        repeat = imports_steps.upload_staged(api, f"{tag}-r.csv", statement.to_csv())["batch"]
        payment = matching_payment(api, repeat["id"], donor, source)
        review_steps.decide(api, repeat["id"], 1, already_recorded(donor, payment))
        summary = review_steps.create_preview(api, repeat["id"])["preview"]["summary"]
        execution_steps.commit_import(api, repeat["id"])
        card = donors_steps.get_donor(api, donor["id"]).json()
        with soft_assertions():
            assert_that((summary["new-payments"], summary["duplicate-references"])).described_as(
                "the repeated row should be a reference, not a new payment"
            ).is_equal_to((0, 1))
            assert_that(card["donations-total"]).described_as(
                "the existing payment should not be counted twice"
            ).is_equal_to(2)

    def test_an_exact_repeat_returns_the_original_receipt(
        self, api: AlmaSpeiApi, committed_import: CommittedImport, donor: dict[str, Any]
    ):
        # 1. Commit a batch (fixture)
        # 2. Send exactly the same commit request again
        # 3. Verification: 200 with the same commit; the donor still holds two payments
        response = execution_steps.submit_commit(api, committed_import.request)
        card = donors_steps.get_donor(api, donor["id"]).json()
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "repeating a commit")
            assert_that(response.json()["commit"]["id"]).described_as(
                "a repeat should return the original commit"
            ).is_equal_to(committed_import.commit_id)
            assert_that(card["donations-total"]).described_as(
                "a repeat should not apply the payments again"
            ).is_equal_to(2)

    def test_a_repeat_with_different_details_is_refused(
        self, api: AlmaSpeiApi, committed_import: CommittedImport
    ):
        # 1. Commit a batch (fixture)
        # 2. Send the commit again naming another backup receipt
        # 3. Verification: 409 different-request
        changed = {**committed_import.request, "backup-id": str(uuid.uuid4())}
        response = execution_steps.submit_commit(api, changed)
        assert_error(response, HTTPStatus.CONFLICT, ExecutionErrorPayload.DIFFERENT_REQUEST)

    def test_a_committed_batch_leaves_the_review_queue(
        self, api: AlmaSpeiApi, committed_import: CommittedImport
    ):
        # 1. Commit a batch (fixture)
        # 2. Read the review queue
        # 3. Verification: the batch no longer awaits review
        queued = [b["id"] for b in imports_steps.review_queue(api, limit=100).json()["batches"]]
        assert_that(queued).does_not_contain(committed_import.batch_id)


@allure.feature("Import commit")
class TestCommitRefusals(BaseApiTest):
    def test_a_commit_without_a_valid_receipt_is_refused(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Build a valid approval, then name a receipt that does not exist
        # 2. Verification: 409 backup-required; the donor got no payment and the batch is in review
        batch_id = decided_upload["batch"]["id"]
        request = {
            **execution_steps.approval_request(api, batch_id),
            "backup-id": str(uuid.uuid4()),
        }
        response = execution_steps.submit_commit(api, request)
        with soft_assertions():
            assert_error(response, HTTPStatus.CONFLICT, ExecutionErrorPayload.BACKUP_REQUIRED)
            assert_nothing_applied(api, batch_id, donor)

    def test_a_changed_effect_digest_is_refused(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Build a valid approval with a different effect digest
        # 2. Verification: 409 stale-preview and nothing applied
        batch_id = decided_upload["batch"]["id"]
        request = {**execution_steps.approval_request(api, batch_id), "effect-digest": "0" * 64}
        response = execution_steps.submit_commit(api, request)
        with soft_assertions():
            assert_error(response, HTTPStatus.CONFLICT, ExecutionErrorPayload.CHANGED_PREVIEW)
            assert_nothing_applied(api, batch_id, donor)

    def test_a_catalogue_change_after_the_preview_is_refused(
        self,
        api: AlmaSpeiApi,
        decided_upload: dict[str, Any],
        donor: dict[str, Any],
        donor_factory: DonorFactory,
        tag: str,
    ):
        # 1. Build a valid approval
        # 2. Create an unrelated donor (the catalogue moves on)
        # 3. Commit the approval
        # 4. Verification: 409 stale-catalog and nothing applied - old overlap checks are void
        batch_id = decided_upload["batch"]["id"]
        request = execution_steps.approval_request(api, batch_id)
        donor_factory(new_donor_profile(tag=tag))
        response = execution_steps.submit_commit(api, request)
        with soft_assertions():
            assert_error(response, HTTPStatus.CONFLICT, ReviewErrorPayload.STALE_CATALOG)
            assert_nothing_applied(api, batch_id, donor)

    def test_a_catalogue_change_marks_decisions_for_re_review(
        self,
        api: AlmaSpeiApi,
        decided_upload: dict[str, Any],
        donor_factory: DonorFactory,
        tag: str,
    ):
        # 1. Decide both rows (fixture), then create an unrelated donor
        # 2. Read the readiness blockers
        # 3. Verification: both rows block as stale-catalog until they are reviewed again
        donor_factory(new_donor_profile(tag=tag))
        body = review_steps.read_blockers(api, decided_upload["batch"]["id"]).json()
        assert_that([(b["row-number"], b["code"]) for b in body["blockers"]]).described_as(
            "a canonical change should require fresh review of every decision"
        ).is_equal_to([(1, BlockerCode.STALE_CATALOG), (2, BlockerCode.STALE_CATALOG)])

    def test_an_unconfirmed_commit_is_rejected(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Build a valid approval without the explicit confirmation
        # 2. Verification: 400 import validation
        request = {
            **execution_steps.approval_request(api, decided_upload["batch"]["id"]),
            "confirmed": False,
        }
        response = execution_steps.submit_commit(api, request)
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    def test_a_commit_without_csrf_is_refused(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Send a valid approval without the X-CSRF-Token header
        # 2. Verification: 403 csrf
        request = execution_steps.approval_request(api, decided_upload["batch"]["id"])
        response = execution_steps.submit_commit(api, request, headers={Header.CSRF_TOKEN: None})
        assert_error(response, HTTPStatus.FORBIDDEN, ReviewErrorPayload.CSRF)


# --- file-local helpers -------------------------------------------------------
def staged_amounts(api: AlmaSpeiApi, batch_id: str) -> list[Decimal]:
    rows = imports_steps.read_rows(api, batch_id).json()["rows"]
    return [Decimal(row["payload"]["amount"]) for row in rows]


def matching_payment(
    api: AlmaSpeiApi, batch_id: str, donor: dict[str, Any], source: dict[str, Any]
) -> dict[str, Any]:
    """The donor's payment with the source row's date and amount (exactly one expected)."""
    payments = review_steps.lookup_payments(api, batch_id, [("donor-id", donor["id"])]).json()
    matches = [
        p
        for p in payments["payments"]
        if p["received-on"] == source["date"] and Decimal(p["amount"]) == Decimal(source["amount"])
    ]
    assert_that(matches).described_as("one recorded payment should match the row").is_length(1)
    return matches[0]


def assert_nothing_applied(api: AlmaSpeiApi, batch_id: str, donor: dict[str, Any]):
    """A refused commit leaves the batch in review and the donor without payments."""
    outcome = execution_steps.read_outcome(api, batch_id).json()
    card = donors_steps.get_donor(api, donor["id"]).json()
    with soft_assertions():
        assert_that((outcome["batch"]["state"], outcome["commit"])).described_as(
            "a refused commit should leave the batch in review, uncommitted"
        ).is_equal_to((ImportState.REVIEW, None))
        assert_that(card["donations-total"]).described_as(
            "a refused commit should write no payment"
        ).is_equal_to(0)
