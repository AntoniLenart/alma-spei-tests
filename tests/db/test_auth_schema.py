"""Database tests for the authentication schema (task 57).

Migration 202610250002-auth creates the account, credential, session and
security audit tables. Accounts are deactivated rather than deleted, sessions
are deleted on logout, and the security audit is append-only. A session row
stores only SHA-256 digests of its tokens, never a token itself. Constraint
probes insert as the app role inside a transaction that is always rolled back.
"""

import base64
import hashlib
from datetime import timedelta

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import SESSION_LIFETIME_HOURS, Privilege
from alma_spei_tests.data import ProvisionedAccount
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps
from alma_spei_tests.testbase import BaseDbTest

AUTH_TABLES = ("users", "local_credentials", "sessions", "security_audit_events")
ALL_PRIVILEGES = tuple(Privilege)

#: Accounts and credentials are edited and deactivated, never deleted.
EDIT_ONLY = {
    Privilege.SELECT: True,
    Privilege.INSERT: True,
    Privilege.UPDATE: True,
    Privilege.DELETE: False,
    Privilege.TRUNCATE: False,
}
#: Sessions end by deletion (logout, expiry clean-up), but are never truncated.
SESSION_GRANTS = {**EDIT_ONLY, Privilege.DELETE: True}
#: The security audit is read and appended only.
APPEND_ONLY = {
    Privilege.SELECT: True,
    Privilege.INSERT: True,
    Privilege.UPDATE: False,
    Privilege.DELETE: False,
    Privilege.TRUNCATE: False,
}


@allure.feature("Authentication schema")
class TestAuthTables(BaseDbTest):
    def test_the_migration_creates_the_authentication_tables(self, db: DbQueries):
        # 1. Look the authentication tables up
        # 2. Verification: accounts, credentials, sessions and the security audit all exist
        assert_that(db_steps.read_tables_present(db, AUTH_TABLES)).described_as(
            "the auth migration should create its four tables"
        ).is_equal_to(dict.fromkeys(AUTH_TABLES, True))

    @pytest.mark.parametrize(
        ("table", "grants"),
        [
            pytest.param("users", EDIT_ONLY, id="users"),
            pytest.param("local_credentials", EDIT_ONLY, id="local_credentials"),
            pytest.param("sessions", SESSION_GRANTS, id="sessions"),
            pytest.param("security_audit_events", APPEND_ONLY, id="security_audit_events"),
        ],
    )
    def test_the_app_role_has_only_the_privileges_it_needs(
        self, db: DbQueries, table: str, grants: dict[Privilege, bool]
    ):
        # 1. Read the app role's privileges on the table
        # 2. Verification: exactly the expected grants
        assert_that(db_steps.read_privileges(db, table, ALL_PRIVILEGES)).described_as(
            f"the app role's privileges on {table} should be least-privilege"
        ).is_equal_to(grants)

    def test_a_valid_account_row_is_accepted(self, db: DbQueries):
        # 1. Insert a valid account as the app role (rolled back)
        # 2. Verification: no constraint rejects it, so each probe below tests one rule
        assert_that(db_steps.probe_user(db)).described_as(
            "a valid account should satisfy every constraint"
        ).is_none()

    @pytest.mark.parametrize(
        ("changes", "constraint"),
        [
            pytest.param({"username": "QA.Upper"}, "users_username_check", id="upper-case"),
            pytest.param({"username": "qa"}, "users_username_check", id="too-short"),
            pytest.param({"username": "qa user"}, "users_username_check", id="space"),
            pytest.param({"display_name": "  "}, "users_display_name_check", id="blank-name"),
        ],
    )
    def test_account_constraints_reject_invalid_rows(
        self, db: DbQueries, changes: dict[str, object], constraint: str
    ):
        # 1. Insert an account breaking one rule (rolled back)
        # 2. Verification: the database names the violated constraint
        assert_that(db_steps.probe_user(db, **changes)).described_as(
            f"the database should enforce {constraint}"
        ).is_equal_to(constraint)

    def test_usernames_are_unique(self, db: DbQueries, settings: Settings):
        # 1. Insert an account with the QA administrator's username (rolled back)
        # 2. Verification: the unique constraint rejects it
        assert_that(db_steps.probe_user(db, username=settings.admin_username)).described_as(
            "a second account with the same username should be rejected"
        ).is_equal_to("users_username_key")


@allure.feature("Authentication schema")
class TestSessionStorage(BaseDbTest):
    def test_a_session_stores_only_digests_of_its_tokens(
        self, staff_api: AlmaSpeiApi, staff: ProvisionedAccount, db: DbQueries
    ):
        # 1. Sign a staff account in and read its stored session
        # 2. Verification: the row holds the SHA-256 digests of the session and CSRF tokens,
        #    and neither token itself
        session_token = staff_api.session.session_token or ""
        csrf_token = staff_api.session.csrf_token or ""
        stored = db_steps.read_sessions(db, staff.id)
        with soft_assertions():
            assert_that([(s["token_digest"], s["csrf_digest"]) for s in stored]).described_as(
                "the session should be stored by its token digests"
            ).is_equal_to([(digest(session_token), digest(csrf_token))])
            assert_that(str(stored)).described_as(
                "no stored session column should hold a raw token"
            ).does_not_contain(session_token).does_not_contain(csrf_token)

    def test_a_session_expires_eight_hours_after_it_began(
        self, staff_api: AlmaSpeiApi, staff: ProvisionedAccount, db: DbQueries
    ):
        # 1. Sign a staff account in and read its stored session
        # 2. Verification: its absolute expiry is 8 hours after its creation
        stored = db_steps.read_sessions(db, staff.id)[0]
        assert_that(stored["expires_at"] - stored["created_at"]).described_as(
            "a session should live at most 8 hours"
        ).is_equal_to(timedelta(hours=SESSION_LIFETIME_HOURS))


# --- file-local helpers -------------------------------------------------------
def digest(token: str) -> str:
    """The app's token digest: SHA-256, base64url with padding."""
    return base64.urlsafe_b64encode(hashlib.sha256(token.encode()).digest()).decode()
