"""API tests for account administration (administrators only)."""

import uuid
from collections.abc import Callable
from http import HTTPStatus

import allure
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import KNOWN_PASSWORD, ApiErrorPayload
from alma_spei_tests.data import ProvisionedAccount, SyntheticAccount, new_account
from alma_spei_tests.steps import auth_steps, donors_steps
from alma_spei_tests.testbase import BaseApiTest

#: Display name used when an edit only flips flags.
EDITED_DISPLAY_NAME = "QA Edited Account"

#: Violates the username pattern ``^[A-Za-z0-9._-]{3,64}$``.
USERNAME_WITH_SPACE = "qa invalid"

#: Principal fields compared by the listing test (``id`` is random).
PRINCIPAL_FIELDS = (
    "username",
    "display-name",
    "active",
    "administrator",
    "password-change-required",
)


@allure.feature("Accounts")
class TestAccountCreation(BaseApiTest):
    def test_admin_creates_an_account_with_a_temporary_password(
        self, api: AlmaSpeiApi, account_factory: Callable[..., ProvisionedAccount]
    ):
        # 1. Create a non-admin account as the administrator
        # 2. List accounts
        # 3. Verification: the account is listed, active, non-admin, and must change its password
        provisioned = account_factory()
        listed = find_account(auth_steps.list_accounts(api).json()["users"], provisioned.id)
        assert_that(project(listed)).described_as(
            "new account should be active, non-admin and require a password change"
        ).is_equal_to(
            {
                "username": provisioned.username,
                "display-name": provisioned.display_name,
                "active": True,
                "administrator": False,
                "password-change-required": True,
            }
        )

    def test_usernames_are_unique_regardless_of_case(
        self, api: AlmaSpeiApi, account_factory: Callable[..., ProvisionedAccount]
    ):
        # 1. Create an account
        # 2. Request another account with the same username in upper case
        # 3. Verification: HTTP 409 username-exists
        provisioned = account_factory()
        duplicate = SyntheticAccount(provisioned.username.upper(), provisioned.display_name)
        response = auth_steps.request_account(api, duplicate)
        assert_error(response, HTTPStatus.CONFLICT, ApiErrorPayload.USERNAME_EXISTS)

    def test_invalid_username_is_rejected(self, api: AlmaSpeiApi):
        # 1. Request an account whose username contains a space
        # 2. Verification: HTTP 422 validation
        invalid = SyntheticAccount(USERNAME_WITH_SPACE, new_account().display_name)
        response = auth_steps.request_account(api, invalid)
        assert_error(response, HTTPStatus.UNPROCESSABLE_ENTITY, ApiErrorPayload.AUTH_VALIDATION)


@allure.feature("Accounts")
class TestAccountAdministration(BaseApiTest):
    def test_admin_edits_display_name_and_role(self, api: AlmaSpeiApi, staff: ProvisionedAccount):
        # 1. Edit a staff account's display name and grant it administration
        # 2. Verification: HTTP 200 and the account reflects both changes
        response = auth_steps.edit_account(
            api, staff.id, EDITED_DISPLAY_NAME, active=True, administrator=True
        )
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "editing an account")
            assert_that(
                project(response.json()["user"], "display-name", "administrator")
            ).described_as("edited account should carry the new name and role").is_equal_to(
                {"display-name": EDITED_DISPLAY_NAME, "administrator": True}
            )

    def test_last_active_administrator_cannot_be_demoted(
        self, api: AlmaSpeiApi, settings: Settings
    ):
        # 1. Remove administration from the only active administrator (the QA admin)
        # 2. Verification: HTTP 409 last-administrator, and the session still works
        me = api.signed_in_user()
        response = auth_steps.edit_account(
            api, me["id"], settings.admin_display_name, active=True, administrator=False
        )
        with soft_assertions():
            assert_error(response, HTTPStatus.CONFLICT, ApiErrorPayload.LAST_ADMINISTRATOR)
            assert_that(api.signed_in_user()["administrator"]).described_as(
                "the administrator should keep the role"
            ).is_true()

    def test_unknown_account_is_not_found(self, api: AlmaSpeiApi):
        # 1. Edit an account id that does not exist
        # 2. Verification: HTTP 404 account not-found
        response = auth_steps.edit_account(
            api, str(uuid.uuid4()), EDITED_DISPLAY_NAME, active=True, administrator=False
        )
        assert_error(response, HTTPStatus.NOT_FOUND, ApiErrorPayload.ACCOUNT_NOT_FOUND)

    def test_password_reset_ends_sessions_and_issues_a_temporary_password(
        self, api: AlmaSpeiApi, staff: ProvisionedAccount, staff_api: AlmaSpeiApi
    ):
        # 1. Reset the password of a signed-in staff account
        # 2. Use the staff session again
        # 3. Verification: a new temporary password, the flag set, and the old session answers 401
        response = auth_steps.reset_password(api, staff.id)
        donors = donors_steps.list_donors(staff_api)
        body = response.json()
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "resetting a password")
            assert_that(body["temporary-password"]).described_as(
                "reset should issue a new temporary password"
            ).is_not_equal_to(staff.temporary_password)
            assert_that(body["user"]["password-change-required"]).described_as(
                "reset should require a password change"
            ).is_true()
            assert_error(donors, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)

    def test_deactivation_ends_sessions_and_blocks_login(
        self,
        api: AlmaSpeiApi,
        anonymous_api: AlmaSpeiApi,
        staff: ProvisionedAccount,
        staff_api: AlmaSpeiApi,
    ):
        # 1. Deactivate a signed-in staff account
        # 2. Use the staff session again, then try to log in afresh
        # 3. Verification: the session answers 401 and the login is refused as invalid credentials
        auth_steps.deactivate_account(api, staff.id, staff.display_name)
        donors = donors_steps.list_donors(staff_api)
        login = auth_steps.login(anonymous_api, staff.username, KNOWN_PASSWORD)
        with soft_assertions():
            assert_error(donors, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)
            assert_error(login, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.INVALID_CREDENTIALS)


@allure.feature("Accounts")
class TestAccountAuthorization(BaseApiTest):
    def test_staff_cannot_list_accounts(self, staff_api: AlmaSpeiApi):
        # 1. List accounts as a signed-in, non-admin account
        # 2. Verification: HTTP 403 forbidden
        response = auth_steps.list_accounts(staff_api)
        assert_error(response, HTTPStatus.FORBIDDEN, ApiErrorPayload.FORBIDDEN)

    def test_anonymous_client_cannot_list_accounts(self, anonymous_api: AlmaSpeiApi):
        # 1. List accounts without signing in
        # 2. Verification: HTTP 401 unauthenticated
        response = auth_steps.list_accounts(anonymous_api)
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)


# --- file-local helpers -------------------------------------------------------
def find_account(users: list[dict], account_id: str) -> dict:
    """The listed account with ``account_id``; fails when it is not listed."""
    account = next((user for user in users if user["id"] == account_id), None)
    if account is None:
        raise AssertionError(f"new account {account_id} should be listed")
    return account


def project(user: dict, *fields: str) -> dict:
    """The given principal fields (default: all but ``id``)."""
    return {field: user.get(field) for field in fields or PRINCIPAL_FIELDS}
