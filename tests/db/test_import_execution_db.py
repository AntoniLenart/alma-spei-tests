"""Database tests for committing and undoing imports (task 39).

Migration 202611150002-import-execution attributes imported donors and payments
to their batch (``import_batch_id``), records commits, applied items, undos and
payment reversals as append-only history, and excludes reversed payments from
the ``active_donations`` view every normal read uses. Undo compensates instead
of deleting: originals stay, reversals and archived profiles are added.
"""

from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import AuditAction, ImportEvent, PreviewItemKind, Privilege
from alma_spei_tests.data import BankStatement, new_donor_profile, proposed_donor, sha256_hex
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, execution_steps, review_steps
from alma_spei_tests.steps.execution_steps import CommittedImport
from alma_spei_tests.testbase import BaseDbTest

EXECUTION_TABLES = (
    "import_backup_runs",
    "import_commits",
    "import_commit_items",
    "import_undos",
    "donation_reversals",
)
#: Donor columns the app role may still update (profile edits and archiving).
DONOR_UPDATABLE = ("name", "city", "is_active", "version", "updated_by", "updated_at")
#: Donor columns fixed once written: identity, authorship and import attribution.
DONOR_FIXED = ("id", "created_by", "created_at", "import_batch_id")


@allure.feature("Import commit")
class TestCommitProvenance(BaseDbTest):
    def test_committed_payments_are_attributed_to_their_batch(
        self, db: DbQueries, committed_import: CommittedImport, donor: dict[str, Any]
    ):
        # 1. Commit a batch for an existing donor (fixture)
        # 2. Count the records attributed to the batch and read the donor's attribution
        # 3. Verification: two attributed, active payments and no created donor; the existing
        #    donor keeps its manual origin; the lifecycle is reviewed -> approved -> committed
        attribution = db_steps.read_import_attribution(db, committed_import.batch_id)
        events = [e for e, _ in db_steps.read_import_events(db, committed_import.batch_id)]
        with soft_assertions():
            assert_that(attribution).described_as(
                "both payments should carry the batch id"
            ).is_equal_to({"donors": 0, "donations": 2, "active_donations": 2, "reversals": 0})
            assert_that(db_steps.read_donor_import_batch(db, donor["id"])).described_as(
                "an existing donor should not be relabelled by the import"
            ).is_none()
            assert_that(events[-2:]).described_as(
                "approval and commit should be recorded in order"
            ).is_equal_to([ImportEvent.APPROVED, ImportEvent.COMMITTED])

    def test_a_created_donor_is_attributed_and_audited(
        self, api: AlmaSpeiApi, db: DbQueries, staged_batch_id: str, tag: str, admin_id: str
    ):
        # 1. Commit a batch whose rows created one proposed donor
        # 2. Read the donor's attribution and audit
        # 3. Verification: the donor carries the batch id and an audited creation
        proposal = review_steps.create_proposal(
            api, staged_batch_id, new_donor_profile(tag=tag).to_payload()
        )
        review_steps.decide_rows(
            api, staged_batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        committed = execution_steps.commit_import(api, staged_batch_id)
        created_id = created_donor_id(api, committed)
        with soft_assertions():
            assert_that(db_steps.read_donor_import_batch(db, created_id)).described_as(
                "the created donor should carry the batch id"
            ).is_equal_to(committed.batch_id)
            assert_that(db_steps.read_donor_audit_actions(db, created_id)).described_as(
                "the creation should be audited"
            ).is_equal_to([AuditAction.CREATE])

    def test_commit_advances_the_catalogue_revision(
        self, api: AlmaSpeiApi, db: DbQueries, decided_upload: dict[str, Any]
    ):
        # 1. Read the catalogue revision, then commit a decided batch
        # 2. Verification: the revision moved on (earlier overlap checks are now void)
        before = db_steps.read_catalog_revision(db)
        execution_steps.commit_import(api, decided_upload["batch"]["id"])
        assert_that(db_steps.read_catalog_revision(db)).described_as(
            "a commit should advance the catalogue revision"
        ).is_greater_than(before)

    def test_a_refused_commit_writes_nothing(
        self, api: AlmaSpeiApi, db: DbQueries, decided_upload: dict[str, Any]
    ):
        # 1. Snapshot the batch and the active catalogue
        # 2. Send a valid approval with a different effect digest (refused)
        # 3. Verification: no attributed record, no approval event, the same active counts
        batch_id = decided_upload["batch"]["id"]
        request = execution_steps.approval_request(api, batch_id)
        before = (
            db_steps.read_active_catalog_counts(db),
            db_steps.read_import_events(db, batch_id),
        )
        execution_steps.submit_commit(api, {**request, "effect-digest": "0" * 64})
        after = (db_steps.read_active_catalog_counts(db), db_steps.read_import_events(db, batch_id))
        with soft_assertions():
            assert_that(db_steps.read_import_attribution(db, batch_id)).described_as(
                "a refused commit should leave no attributed record"
            ).is_equal_to({"donors": 0, "donations": 0, "active_donations": 0, "reversals": 0})
            assert_that(after).described_as(
                "a refused commit should change neither the catalogue nor the lifecycle"
            ).is_equal_to(before)


@allure.feature("Import undo")
class TestUndoCompensation(BaseDbTest):
    def test_commit_and_undo_return_the_active_catalogue_to_its_start(
        self, api: AlmaSpeiApi, db: DbQueries, staged_batch_id: str, tag: str
    ):
        # 1. Count active donors and payments
        # 2. Commit a batch creating one donor with two payments, and count again
        # 3. Undo it and count again
        # 4. Verification: +1 donor and +2 payments after the commit; back to the start after
        #    the undo, with both original payments retained and reversed
        start = db_steps.read_active_catalog_counts(db)
        proposal = review_steps.create_proposal(
            api, staged_batch_id, new_donor_profile(tag=tag).to_payload()
        )
        review_steps.decide_rows(
            api, staged_batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        committed = execution_steps.commit_import(api, staged_batch_id)
        applied = db_steps.read_active_catalog_counts(db)
        execution_steps.undo_import(api, committed)
        undone = db_steps.read_active_catalog_counts(db)
        with soft_assertions():
            assert_that(applied).described_as(
                "the commit should add the batch's donor and payments"
            ).is_equal_to({"donors": start["donors"] + 1, "donations": start["donations"] + 2})
            assert_that(undone).described_as(
                "the undo should return the active catalogue to its start"
            ).is_equal_to(start)
            assert_that(db_steps.read_import_attribution(db, committed.batch_id)).described_as(
                "the originals should stay, compensated by reversals"
            ).is_equal_to({"donors": 1, "donations": 2, "active_donations": 0, "reversals": 2})

    def test_undo_archives_the_created_donor_with_an_audit(
        self, api: AlmaSpeiApi, db: DbQueries, staged_batch_id: str, tag: str
    ):
        # 1. Commit a batch creating one donor, then undo it
        # 2. Read the donor's row and audit
        # 3. Verification: archived (not deleted), audited as create then archive
        proposal = review_steps.create_proposal(
            api, staged_batch_id, new_donor_profile(tag=tag).to_payload()
        )
        review_steps.decide_rows(
            api, staged_batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        committed = execution_steps.commit_import(api, staged_batch_id)
        created_id = created_donor_id(api, committed)
        execution_steps.undo_import(api, committed)
        with soft_assertions():
            assert_that(db_steps.read_donor(db, created_id)["is_active"]).described_as(
                "the created donor should be archived, not deleted"
            ).is_false()
            assert_that(db_steps.read_donor_audit_actions(db, created_id)).described_as(
                "the archiving should be audited"
            ).is_equal_to([AuditAction.CREATE, AuditAction.ARCHIVE])

    def test_reimport_keeps_both_attempts(
        self,
        api: AlmaSpeiApi,
        db: DbQueries,
        committed_import: CommittedImport,
        bank_statement: BankStatement,
        tag: str,
    ):
        # 1. Undo a committed batch and re-import its file
        # 2. Verification: the file now has two attempts on record
        undone = execution_steps.undo_import(api, committed_import)["batch"]
        api.imports.retry(undone["id"], undone["version"], f"{tag}.csv", bank_statement.to_csv())
        file_hash = sha256_hex(bank_statement.to_csv())
        assert_that(db_steps.count_import_attempts(db, file_hash)).described_as(
            "the undone attempt should stay beside the fresh one"
        ).is_equal_to(2)


@allure.feature("Import schema")
class TestExecutionGrants(BaseDbTest):
    @pytest.mark.parametrize("table", EXECUTION_TABLES)
    def test_execution_history_is_append_only(self, db: DbQueries, table: str):
        # 1. Read the app role's privileges on the table
        # 2. Verification: read and insert only
        granted = db_steps.read_privileges(
            db,
            table,
            [
                Privilege.SELECT,
                Privilege.INSERT,
                Privilege.UPDATE,
                Privilege.DELETE,
                Privilege.TRUNCATE,
            ],
        )
        assert_that(granted).described_as(f"{table} should be append-only").is_equal_to(
            {
                Privilege.SELECT: True,
                Privilege.INSERT: True,
                Privilege.UPDATE: False,
                Privilege.DELETE: False,
                Privilege.TRUNCATE: False,
            }
        )

    def test_donor_attribution_cannot_be_rewritten(self, db: DbQueries):
        # 1. Read the app role's column UPDATE privileges on donors
        # 2. Verification: profile and archive columns are updatable; identity, authorship and
        #    import attribution are not
        with soft_assertions():
            assert_that(
                db_steps.read_column_privileges(db, "donors", DONOR_UPDATABLE, Privilege.UPDATE)
            ).described_as("profile edits and archiving should stay possible").is_equal_to(
                dict.fromkeys(DONOR_UPDATABLE, True)
            )
            assert_that(
                db_steps.read_column_privileges(db, "donors", DONOR_FIXED, Privilege.UPDATE)
            ).described_as("donor identity and attribution should be fixed").is_equal_to(
                dict.fromkeys(DONOR_FIXED, False)
            )


# --- file-local helpers -------------------------------------------------------
def created_donor_id(api: AlmaSpeiApi, committed: CommittedImport) -> str:
    """The donor the commit created (its single new-donor item)."""
    items = execution_steps.read_commit_items(api, committed.batch_id).json()["items"]
    return next(i["donor-id"] for i in items if i["kind"] == PreviewItemKind.NEW_DONOR)
