"""Database tests for review decisions, proposals and previews (task 38).

Migration 202611150001-review-decisions adds five tables. Decisions, proposals,
their journal and previews are review metadata only: nothing reaches the donor
and payment tables before an approved commit (task 39). The app role may insert
and read them, update only a decision's or proposal's mutable columns, and never
delete or rewrite the journal or a preview.
"""

from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    DecisionKind,
    ImportEvent,
    Privilege,
    ReviewEventType,
)
from alma_spei_tests.data import existing_donor, new_donor_profile, proposed_donor
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, review_steps
from alma_spei_tests.testbase import BaseDbTest

REVIEW_TABLES = (
    "import_donor_proposals",
    "import_review_decisions",
    "import_review_events",
    "import_previews",
    "import_preview_items",
)
#: Immutable once written: the journal and the preview snapshot.
IMMUTABLE_TABLES = ("import_review_events", "import_previews", "import_preview_items")

PROPOSAL_UPDATABLE = ("profile", "version", "updated_by", "updated_at")
PROPOSAL_FIXED = ("id", "batch_id", "created_by", "created_at")
DECISION_UPDATABLE = ("version", "kind", "donor_id", "financial", "complete", "reviewer_id")
DECISION_FIXED = ("batch_id", "worksheet_index", "row_number")


@allure.feature("Review decisions")
class TestReviewPersistence(BaseDbTest):
    def test_a_saved_decision_is_stored_with_its_reviewer(
        self,
        api: AlmaSpeiApi,
        db: DbQueries,
        staged_batch_id: str,
        donor: dict[str, Any],
        admin_id: str,
    ):
        # 1. Save a complete decision for row 1
        # 2. Read the stored decision, the review journal and the batch events
        # 3. Verification: stored as complete for the donor by the admin; journaled as
        #    decision-saved; the batch lifecycle records a reviewed event
        review_steps.decide(api, staged_batch_id, 1, existing_donor(donor))
        stored = db_steps.read_review_decision(db, staged_batch_id, 1)
        with soft_assertions():
            assert_that(
                (stored["kind"], stored["donor_id"], stored["complete"], stored["reviewer_id"])
            ).described_as("the decision should be stored as saved, by its reviewer").is_equal_to(
                (DecisionKind.EXISTING_DONOR, donor["id"], True, admin_id)
            )
            assert_that(db_steps.read_review_events(db, staged_batch_id)).described_as(
                "the review journal should record the save"
            ).is_equal_to([ReviewEventType.DECISION_SAVED])
            assert_that(
                [e for e, _ in db_steps.read_import_events(db, staged_batch_id)]
            ).described_as("the batch lifecycle should record the review").contains(
                ImportEvent.REVIEWED
            )

    def test_review_writes_nothing_canonical(
        self, api: AlmaSpeiApi, db: DbQueries, staged_batch_id: str, tag: str
    ):
        # 1. Count the canonical donor tables
        # 2. Propose a donor, link both rows to it and prepare a preview
        # 3. Verification: donors, donations and their audit are unchanged; one preview exists
        before = db_steps.read_canonical_counts(db)
        proposal = review_steps.create_proposal(
            api, staged_batch_id, new_donor_profile(tag=tag).to_payload()
        )
        review_steps.decide_rows(
            api, staged_batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        review_steps.create_preview(api, staged_batch_id)
        with soft_assertions():
            assert_that(db_steps.read_canonical_counts(db)).described_as(
                "review and preview should not write donors, donations or their audit"
            ).is_equal_to(before)
            assert_that(db_steps.count_previews(db, staged_batch_id)).described_as(
                "the preview should be recorded"
            ).is_equal_to(1)

    def test_a_proposal_stores_only_the_typed_profile(
        self, api: AlmaSpeiApi, db: DbQueries, staged_batch_id: str, tag: str
    ):
        # 1. Propose a donor whose name has surrounding spaces
        # 2. Verification: the stored profile is trimmed and carries exactly the profile fields
        profile = new_donor_profile(tag=tag)
        padded = profile.with_changes(name=f"  {profile.name}  ")
        proposal = review_steps.create_proposal(api, staged_batch_id, padded.to_payload())
        stored = db_steps.read_proposal_profile(db, proposal["id"])
        assert_that(stored).described_as(
            "the stored proposal should be the normalized profile"
        ).is_equal_to(profile.to_payload())


@allure.feature("Review schema")
class TestReviewGrants(BaseDbTest):
    @pytest.mark.parametrize("table", REVIEW_TABLES)
    def test_the_app_role_reads_and_inserts_but_never_deletes(self, db: DbQueries, table: str):
        # 1. Read the app role's table privileges
        # 2. Verification: SELECT and INSERT, no DELETE or TRUNCATE
        granted = db_steps.read_privileges(
            db, table, [Privilege.SELECT, Privilege.INSERT, Privilege.DELETE, Privilege.TRUNCATE]
        )
        assert_that(granted).described_as(
            f"the app role should read and insert {table} rows but never delete them"
        ).is_equal_to(
            {
                Privilege.SELECT: True,
                Privilege.INSERT: True,
                Privilege.DELETE: False,
                Privilege.TRUNCATE: False,
            }
        )

    @pytest.mark.parametrize("table", IMMUTABLE_TABLES)
    def test_the_journal_and_previews_are_immutable(self, db: DbQueries, table: str):
        # 1. Read the app role's UPDATE privilege
        # 2. Verification: none - history and preview snapshots are never rewritten
        granted = db_steps.read_privileges(db, table, [Privilege.UPDATE])
        assert_that(granted[Privilege.UPDATE]).described_as(
            f"the app role should not update {table}"
        ).is_false()

    @pytest.mark.parametrize(
        ("table", "updatable", "fixed"),
        [
            pytest.param(
                "import_donor_proposals", PROPOSAL_UPDATABLE, PROPOSAL_FIXED, id="proposals"
            ),
            pytest.param(
                "import_review_decisions", DECISION_UPDATABLE, DECISION_FIXED, id="decisions"
            ),
        ],
    )
    def test_only_the_mutable_columns_can_be_updated(
        self, db: DbQueries, table: str, updatable: tuple[str, ...], fixed: tuple[str, ...]
    ):
        # 1. Read the app role's column UPDATE privileges
        # 2. Verification: the versioned content can change; the identity columns cannot
        with soft_assertions():
            assert_that(
                db_steps.read_column_privileges(db, table, updatable, Privilege.UPDATE)
            ).described_as(
                f"the app role should update the versioned columns of {table}"
            ).is_equal_to(dict.fromkeys(updatable, True))
            assert_that(
                db_steps.read_column_privileges(db, table, fixed, Privilege.UPDATE)
            ).described_as(
                f"the app role should not update the identity columns of {table}"
            ).is_equal_to(dict.fromkeys(fixed, False))
