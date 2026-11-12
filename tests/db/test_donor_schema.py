"""Database tests for the donor schema: constraints and the app role's grants.

Migration 202611070001-donors creates the donor, donation and donor-audit
tables. Constraint probes insert as the least-privileged app role inside a
transaction that is always rolled back, so they leave no rows behind.
"""

import uuid
from typing import Any

import allure
import pytest
from assertpy import assert_that

from alma_spei_tests.constants import Privilege
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps
from alma_spei_tests.testbase import BaseDbTest

#: Every privilege the grants tests look at.
ALL_PRIVILEGES = tuple(Privilege)

#: The app role reads, creates and edits donors but never deletes them.
DONOR_GRANTS = {
    Privilege.SELECT: True,
    Privilege.INSERT: True,
    Privilege.UPDATE: True,
    Privilege.DELETE: False,
    Privilege.TRUNCATE: False,
}

#: Payments and the donor audit are append-only for the app role.
APPEND_ONLY_GRANTS = {
    Privilege.SELECT: True,
    Privilege.INSERT: True,
    Privilege.UPDATE: False,
    Privilege.DELETE: False,
    Privilege.TRUNCATE: False,
}


@allure.feature("Donor schema")
class TestDonorConstraints(BaseDbTest):
    def test_a_valid_donor_row_is_accepted(self, db: DbQueries, admin_id: str):
        # 1. Insert a minimal valid donor as the app role (rolled back)
        # 2. Verification: nothing is rejected, so each negative probe below tests one rule
        assert_that(db_steps.probe_donor(db, admin_id)).described_as(
            "a valid donor row should satisfy every constraint"
        ).is_none()

    @pytest.mark.parametrize(
        ("changes", "constraint"),
        [
            pytest.param(
                {"entity_type": "household"}, "donors_entity_type_check", id="unknown-type"
            ),
            pytest.param({"name": "   "}, "donors_name_check", id="blank-name"),
            pytest.param({"version": 0}, "donors_version_check", id="version-zero"),
            pytest.param(
                {"created_by": str(uuid.uuid4())}, "donors_created_by_fkey", id="unknown-author"
            ),
        ],
    )
    def test_an_invalid_donor_row_is_rejected(
        self, db: DbQueries, admin_id: str, changes: dict[str, Any], constraint: str
    ):
        # 1. Insert a donor row that breaks one rule (rolled back)
        # 2. Verification: the database rejects it with that rule's constraint
        assert_that(db_steps.probe_donor(db, admin_id, **changes)).described_as(
            f"a donor with {changes} should violate {constraint}"
        ).is_equal_to(constraint)

    def test_a_valid_donation_is_accepted(self, db: DbQueries, admin_id: str):
        # 1. Insert a donor and a minimal valid donation (rolled back)
        # 2. Verification: nothing is rejected
        assert_that(db_steps.probe_donation(db, admin_id)).described_as(
            "a valid donation should satisfy every constraint"
        ).is_none()

    @pytest.mark.parametrize(
        ("changes", "constraint"),
        [
            pytest.param({"amount": "0"}, "donations_amount_check", id="zero-amount"),
            pytest.param({"amount": "NaN"}, "donations_amount_check", id="nan-amount"),
            pytest.param({"currency": "pln"}, "donations_currency_check", id="lower-case-currency"),
            pytest.param(
                {"received_on": "infinity"}, "donations_received_on_check", id="infinite-date"
            ),
        ],
    )
    def test_an_invalid_donation_is_rejected(
        self, db: DbQueries, admin_id: str, changes: dict[str, Any], constraint: str
    ):
        # 1. Insert a donor and a donation that breaks one rule (rolled back)
        # 2. Verification: the database rejects it with that rule's constraint
        assert_that(db_steps.probe_donation(db, admin_id, **changes)).described_as(
            f"a donation with {changes} should violate {constraint}"
        ).is_equal_to(constraint)

    @pytest.mark.parametrize(
        ("action", "field_name", "constraint"),
        [
            pytest.param("create", "name", None, id="valid-entry"),
            pytest.param("delete", "name", "donor_audit_events_action_check", id="unknown-action"),
            pytest.param(
                "update", "version", "donor_audit_changes_field_name_check", id="untracked-field"
            ),
        ],
    )
    def test_the_audit_records_only_known_actions_and_profile_fields(
        self, db: DbQueries, admin_id: str, action: str, field_name: str, constraint: str | None
    ):
        # 1. Insert a donor with one audit event and one field change (rolled back)
        # 2. Verification: only the known actions and the profile fields are accepted
        assert_that(db_steps.probe_donor_audit(db, admin_id, action, field_name)).described_as(
            f"an audit '{action}' of '{field_name}' should violate {constraint or 'nothing'}"
        ).is_equal_to(constraint)


@allure.feature("Donor schema")
class TestDonorGrants(BaseDbTest):
    def test_the_app_role_never_deletes_donors(self, db: DbQueries):
        # 1. Read the app role's privileges on donors
        # 2. Verification: read, create and edit only (archiving is an update)
        assert_that(db_steps.read_privileges(db, "donors", ALL_PRIVILEGES)).described_as(
            "the app role should read, create and edit donors but never delete them"
        ).is_equal_to(DONOR_GRANTS)

    @pytest.mark.parametrize("table", ["donations", "donor_audit_events", "donor_audit_changes"])
    def test_payments_and_the_audit_are_append_only(self, db: DbQueries, table: str):
        # 1. Read the app role's privileges on the table
        # 2. Verification: read and insert only
        assert_that(db_steps.read_privileges(db, table, ALL_PRIVILEGES)).described_as(
            f"{table} should be append-only for the app role"
        ).is_equal_to(APPEND_ONLY_GRANTS)
