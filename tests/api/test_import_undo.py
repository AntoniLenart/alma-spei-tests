"""API tests for undoing the latest import and re-importing its file (task 39).

Only the latest commit ever made can be undone, once. Undo compensates instead of
deleting: imported payments leave the active payment history, profiles the
import created are archived, and the original records and history stay. It
never overwrites later work - a later edit of an imported profile blocks it.
After an undo the same file may be uploaded again, explicitly, as a fresh
attempt that inherits no decisions.
"""

import uuid
from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_error_includes, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    STAGED_BATCH_VERSION,
    ExecutionErrorPayload,
    ImportErrorPayload,
    ImportState,
    UndoConflict,
)
from alma_spei_tests.data import (
    BankStatement,
    DonorFactory,
    existing_donor,
    new_bank_statement,
    new_donor_profile,
    proposed_donor,
)
from alma_spei_tests.steps import donors_steps, execution_steps, imports_steps, review_steps
from alma_spei_tests.steps.execution_steps import CommittedImport
from alma_spei_tests.testbase import BaseApiTest


@allure.feature("Import undo")
class TestUndoLatest(BaseApiTest):
    def test_undo_reverses_the_payments_and_keeps_the_history(
        self, api: AlmaSpeiApi, committed_import: CommittedImport, donor: dict[str, Any]
    ):
        # 1. Commit a batch that gave an existing donor two payments (fixture)
        # 2. Undo it
        # 3. Verification: 200; the batch is undone with the commit kept; two payments
        #    reversed, no profile archived; the donor (still active) shows no payments
        current = execution_steps.read_outcome(api, committed_import.batch_id).json()
        response = execution_steps.submit_undo(api, execution_steps.undo_payload(current))
        outcome = response.json()
        card = donors_steps.get_donor(api, donor["id"]).json()
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "undoing the latest import")
            assert_that((outcome["batch"]["state"], outcome["commit"]["id"])).described_as(
                "the batch should be undone with its commit retained"
            ).is_equal_to((ImportState.UNDONE, committed_import.commit_id))
            assert_that(
                (outcome["undo"]["reversed-payments"], outcome["undo"]["archived-donors"])
            ).described_as("undo should reverse both payments and archive nobody").is_equal_to(
                (2, 0)
            )
            assert_that((card["donor"]["is-active"], card["donations-total"])).described_as(
                "the existing donor should stay active without the imported payments"
            ).is_equal_to((True, 0))

    def test_undo_archives_the_profile_the_import_created(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Commit a batch whose rows created one proposed donor
        # 2. Undo it
        # 3. Verification: one profile archived; it is no longer listed as active
        proposal = review_steps.create_proposal(
            api, staged_batch_id, new_donor_profile(tag=tag).to_payload()
        )
        review_steps.decide_rows(
            api, staged_batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        committed = execution_steps.commit_import(api, staged_batch_id)
        outcome = execution_steps.undo_import(api, committed)
        with soft_assertions():
            assert_that(outcome["undo"]["archived-donors"]).described_as(
                "the imported profile should be archived"
            ).is_equal_to(1)
            assert_that(donors_steps.list_tagged(api, tag)).described_as(
                "the archived profile should leave the active donor list"
            ).is_empty()

    def test_an_exact_repeat_returns_the_undo_receipt(
        self, api: AlmaSpeiApi, committed_import: CommittedImport
    ):
        # 1. Undo a committed batch
        # 2. Send exactly the same undo again
        # 3. Verification: 200 with the same undo receipt
        current = execution_steps.read_outcome(api, committed_import.batch_id).json()
        payload = execution_steps.undo_payload(current)
        first = execution_steps.submit_undo(api, payload).json()
        again = execution_steps.submit_undo(api, payload)
        with soft_assertions():
            assert_status(again, HTTPStatus.OK, "repeating an undo")
            assert_that(again.json()["undo"]["id"]).described_as(
                "a repeat should return the original undo"
            ).is_equal_to(first["undo"]["id"])

    def test_eligibility_follows_the_commit_and_the_undo(
        self, api: AlmaSpeiApi, committed_import: CommittedImport
    ):
        # 1. Read the undo eligibility of a just committed batch
        # 2. Undo it and read the eligibility again
        # 3. Verification: first eligible for this commit; then refused as already undone
        before = execution_steps.read_undo_eligibility(api, committed_import.batch_id).json()
        execution_steps.undo_import(api, committed_import)
        after = execution_steps.read_undo_eligibility(api, committed_import.batch_id).json()
        assert_that(
            [
                (before["eligible"], before["commit-id"], codes(before)),
                (after["eligible"], codes(after)),
            ]
        ).described_as("only the fresh commit should be undoable").is_equal_to(
            [(True, committed_import.commit_id, []), (False, [UndoConflict.ALREADY_UNDONE])]
        )


@allure.feature("Import undo")
class TestUndoRefusals(BaseApiTest):
    def test_only_the_latest_commit_can_be_undone(
        self,
        api: AlmaSpeiApi,
        committed_import: CommittedImport,
        later_commit: CommittedImport,
    ):
        # 1. Commit a batch, then commit a second one (fixtures)
        # 2. Undo the first batch
        # 3. Verification: 409 undo-blocked naming not-latest; the first batch stays committed
        current = execution_steps.read_outcome(api, committed_import.batch_id).json()
        response = execution_steps.submit_undo(api, execution_steps.undo_payload(current))
        state = execution_steps.read_outcome(api, committed_import.batch_id).json()["batch"][
            "state"
        ]
        with soft_assertions():
            assert_error_includes(response, HTTPStatus.CONFLICT, ExecutionErrorPayload.UNDO_BLOCKED)
            assert_that(codes(response.json())).described_as(
                "the refusal should explain the commit is not the latest"
            ).is_equal_to([UndoConflict.NOT_LATEST])
            assert_that(state).described_as("the older commit should stay applied").is_equal_to(
                ImportState.COMMITTED
            )

    def test_undoing_the_latest_does_not_reopen_the_previous_one(
        self,
        api: AlmaSpeiApi,
        committed_import: CommittedImport,
        later_commit: CommittedImport,
    ):
        # 1. Commit two batches (fixtures) and undo the second
        # 2. Read the first batch's undo eligibility
        # 3. Verification: still not-latest - undo never walks back through history
        execution_steps.undo_import(api, later_commit)
        body = execution_steps.read_undo_eligibility(api, committed_import.batch_id).json()
        assert_that((body["eligible"], codes(body))).described_as(
            "an earlier commit should not become undoable"
        ).is_equal_to((False, [UndoConflict.NOT_LATEST]))

    def test_a_later_edit_of_an_imported_profile_blocks_undo(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Commit a batch whose rows created one proposed donor
        # 2. Edit that donor's city through the donor API
        # 3. Undo the import
        # 4. Verification: 409 undo-blocked (changed-donor); the edit is kept, the donor active
        profile = new_donor_profile(tag=tag)
        proposal = review_steps.create_proposal(api, staged_batch_id, profile.to_payload())
        review_steps.decide_rows(
            api, staged_batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        committed = execution_steps.commit_import(api, staged_batch_id)
        created = donors_steps.list_tagged(api, tag)[0]
        edited = profile.with_changes(city="Nowe Testowo")
        api.donors.update(created["id"], edited.to_update_payload(created["version"]))
        current = execution_steps.read_outcome(api, committed.batch_id).json()
        response = execution_steps.submit_undo(api, execution_steps.undo_payload(current))
        after = donors_steps.get_donor(api, created["id"]).json()["donor"]
        with soft_assertions():
            assert_error_includes(response, HTTPStatus.CONFLICT, ExecutionErrorPayload.UNDO_BLOCKED)
            assert_that(codes(response.json())).described_as(
                "the later edit should be named as the reason"
            ).contains(UndoConflict.CHANGED_DONOR)
            assert_that((after["city"], after["is-active"])).described_as(
                "undo should never overwrite the later edit"
            ).is_equal_to(("Nowe Testowo", True))

    def test_a_batch_under_review_cannot_be_undone(self, api: AlmaSpeiApi, staged_batch_id: str):
        # 1. Read the undo eligibility of a batch still under review
        # 2. Verification: not-committed, no commit id
        body = execution_steps.read_undo_eligibility(api, staged_batch_id).json()
        assert_that((body["eligible"], body["commit-id"], codes(body))).described_as(
            "an uncommitted batch should not be undoable"
        ).is_equal_to((False, None, [UndoConflict.NOT_COMMITTED]))

    def test_undo_naming_another_commit_is_refused(
        self, api: AlmaSpeiApi, committed_import: CommittedImport
    ):
        # 1. Undo a committed batch naming a commit id that is not its commit
        # 2. Verification: 409 ineligible-undo
        current = execution_steps.read_outcome(api, committed_import.batch_id).json()
        payload = {**execution_steps.undo_payload(current), "commit-id": str(uuid.uuid4())}
        response = execution_steps.submit_undo(api, payload)
        assert_error(response, HTTPStatus.CONFLICT, ExecutionErrorPayload.INELIGIBLE_UNDO)


@allure.feature("Import undo")
class TestReimportAfterUndo(BaseApiTest):
    def test_the_undone_file_can_be_uploaded_again_as_a_fresh_attempt(
        self,
        api: AlmaSpeiApi,
        committed_import: CommittedImport,
        bank_statement: BankStatement,
        tag: str,
    ):
        # 1. Undo a committed batch
        # 2. Re-upload the same bytes as an explicit retry of the undone attempt
        # 3. Verification: 201; attempt 2 under review, retrying the undone batch, with no
        #    decision carried over
        undone = execution_steps.undo_import(api, committed_import)["batch"]
        response = imports_steps.retry(
            api, undone["id"], undone["version"], f"{tag}.csv", bank_statement.to_csv()
        )
        batch = response.json()["batch"]
        decision = review_steps.read_decision(api, batch["id"], 1).json()["decision"]
        with soft_assertions():
            assert_status(response, HTTPStatus.CREATED, "re-importing an undone file")
            assert_that(
                (batch["attempt-number"], batch["retry-of"], batch["state"], batch["version"])
            ).described_as("the re-import should be a fresh staged attempt").is_equal_to(
                (2, undone["id"], ImportState.REVIEW, STAGED_BATCH_VERSION)
            )
            assert_that(decision).described_as(
                "no decision should be copied into the new attempt"
            ).is_none()

    def test_a_committed_file_cannot_be_re_imported(
        self,
        api: AlmaSpeiApi,
        committed_import: CommittedImport,
        bank_statement: BankStatement,
        tag: str,
    ):
        # 1. Commit a batch (fixture), without undoing it
        # 2. Re-upload its bytes as a retry
        # 3. Verification: 409 ineligible-retry
        batch = committed_import.outcome["batch"]
        response = imports_steps.retry(
            api, batch["id"], batch["version"], f"{tag}.csv", bank_statement.to_csv()
        )
        assert_error_includes(response, HTTPStatus.CONFLICT, ImportErrorPayload.INELIGIBLE_RETRY)


# --- file-local fixtures and helpers ------------------------------------------
@pytest.fixture
def later_commit(
    api: AlmaSpeiApi,
    committed_import: CommittedImport,
    donor_factory: DonorFactory,
    tag: str,
) -> CommittedImport:
    """A second batch, for another donor, committed after ``committed_import``."""
    other = donor_factory(new_donor_profile(tag=tag))
    later_tag = f"{tag}-later"
    statement = new_bank_statement(later_tag)
    batch = imports_steps.upload_staged(api, f"{later_tag}.csv", statement.to_csv())["batch"]
    review_steps.decide_rows(api, batch["id"], [existing_donor(other), existing_donor(other)])
    return execution_steps.commit_import(api, batch["id"])


def codes(body: dict[str, Any]) -> list[str]:
    return [b["code"] for b in body.get("blockers", [])]
