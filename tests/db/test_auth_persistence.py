"""Database tests for accounts: credential storage, session lifecycle, security audit."""

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import KNOWN_PASSWORD, SecurityEvent
from alma_spei_tests.data import ProvisionedAccount
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import auth_steps, db_steps
from alma_spei_tests.testbase import BaseDbTest

#: buddy-hashers encodes argon2id hashes with this algorithm prefix.
ARGON2ID_PREFIX = "argon2id"


@allure.feature("Account persistence")
class TestCredentialStorage(BaseDbTest):
    def test_password_is_stored_only_as_an_argon2id_hash(self, db: DbQueries, settings: Settings):
        # 1. Read the QA administrator's stored credential
        # 2. Verification: an argon2id hash that does not contain the password; no change pending
        user = db_steps.read_user(db, settings.admin_username)
        with soft_assertions():
            assert_that(user["password_hash"]).described_as(
                "the credential should be an argon2id hash"
            ).starts_with(ARGON2ID_PREFIX)
            assert_that(user["password_hash"]).described_as(
                "the stored hash should not contain the password"
            ).does_not_contain(settings.admin_password)
            assert_that(user["password_change_required"]).described_as(
                "the rotated admin should have no pending password change"
            ).is_false()

    def test_new_account_requires_a_password_change(self, db: DbQueries, staff: ProvisionedAccount):
        # 1. Read a freshly created account's credential row
        # 2. Verification: active, not an administrator, password change required
        user = db_steps.read_user(db, staff.username)
        with soft_assertions():
            assert_that(user["active"]).described_as("new account should be active").is_true()
            assert_that(user["administrator"]).described_as(
                "new account should not be an administrator"
            ).is_false()
            assert_that(user["password_change_required"]).described_as(
                "new account should have to change its temporary password"
            ).is_true()


@allure.feature("Account persistence")
class TestSessionLifecycle(BaseDbTest):
    def test_logout_deletes_the_session_row(
        self, db: DbQueries, staff: ProvisionedAccount, staff_api: AlmaSpeiApi
    ):
        # 1. Count the signed-in staff account's sessions
        # 2. Log it out and count again
        # 3. Verification: one session before, none after
        before = db_steps.count_sessions(db, staff.id)
        auth_steps.logout(staff_api)
        after = db_steps.count_sessions(db, staff.id)
        assert_that((before, after)).described_as(
            "logout should delete the only session"
        ).is_equal_to((1, 0))

    def test_account_lifecycle_is_audited(
        self, db: DbQueries, staff: ProvisionedAccount, staff_api: AlmaSpeiApi
    ):
        # 1. Sign the staff account in (temporary login + rotation) via the fixture
        # 2. Log it out
        # 3. Read the security audit events targeting it
        # 4. Verification: creation, login, password change and logout, in that order
        auth_steps.logout(staff_api)
        events = db_steps.read_security_events(db, staff.id)
        assert_that(events).described_as(
            "the account lifecycle should be audited in order"
        ).is_equal_to(
            [
                SecurityEvent.ACCOUNT_CREATED,
                SecurityEvent.LOGIN,
                SecurityEvent.PASSWORD_CHANGED,
                SecurityEvent.LOGOUT,
            ]
        )

    @pytest.mark.usefixtures("staff_api")
    def test_audit_never_stores_the_password(self, db: DbQueries):
        # 1. Sign a staff account in with a known password (via the fixture)
        # 2. Verification: no security audit row contains that password
        rows = db_steps.count_security_events_mentioning(db, KNOWN_PASSWORD)
        assert_that(rows).described_as(
            "security audit should never contain a password"
        ).is_equal_to(0)
