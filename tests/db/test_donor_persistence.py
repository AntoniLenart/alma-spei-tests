"""Database tests for donors: stored rows, versioning and the transactional audit."""

from typing import Any

import allure
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import INITIAL_DONOR_VERSION, AuditAction
from alma_spei_tests.data import DonorProfile
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, donors_steps
from alma_spei_tests.testbase import BaseDbTest

#: Changed city used by the update scenario.
NEW_CITY = "Testowo Nowe"


@allure.feature("Donor persistence")
class TestDonorPersistence(BaseDbTest):
    def test_created_donor_is_stored_with_its_author(
        self, api: AlmaSpeiApi, db: DbQueries, donor: dict[str, Any], donor_profile: DonorProfile
    ):
        # 1. Create a donor through the API (fixture)
        # 2. Read its row and audit trail from the database
        # 3. Verification: the row matches, is authored by the admin, and one create event exists
        admin_id = api.signed_in_user()["id"]
        row = db_steps.read_donor(db, donor["id"])
        actions = db_steps.read_donor_audit_actions(db, donor["id"])
        with soft_assertions():
            assert_that(row).described_as("the donor row should match the profile").is_equal_to(
                {
                    "name": donor_profile.name,
                    "entity_type": donor_profile.entity_type.value,
                    "city": donor_profile.city,
                    "is_active": True,
                    "version": INITIAL_DONOR_VERSION,
                    "created_by": admin_id,
                    "updated_by": admin_id,
                }
            )
            assert_that(actions).described_as(
                "creation should write exactly one audit event"
            ).is_equal_to([AuditAction.CREATE])

    def test_update_bumps_the_stored_version_and_audits_only_changed_fields(
        self, api: AlmaSpeiApi, db: DbQueries, donor: dict[str, Any], donor_profile: DonorProfile
    ):
        # 1. Change only the donor's city through the API
        # 2. Read the row, the audit actions and the fields of the update event
        # 3. Verification: version 2 with the new city; create + update audited; only city changed
        changed = donor_profile.with_changes(city=NEW_CITY)
        donors_steps.update_donor(api, donor["id"], changed.to_update_payload(donor["version"]))
        row = db_steps.read_donor(db, donor["id"])
        with soft_assertions():
            assert_that((row["city"], row["version"])).described_as(
                "the row should hold the new city at the next version"
            ).is_equal_to((NEW_CITY, INITIAL_DONOR_VERSION + 1))
            assert_that(db_steps.read_donor_audit_actions(db, donor["id"])).described_as(
                "creation and update should both be audited"
            ).is_equal_to([AuditAction.CREATE, AuditAction.UPDATE])
            assert_that(
                db_steps.read_donor_changed_fields(db, donor["id"], AuditAction.UPDATE)
            ).described_as("the update event should record only the city").is_equal_to({"city"})
