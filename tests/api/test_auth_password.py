"""API tests for password changes, including the forced temporary-password rotation."""

from http import HTTPStatus

import allure
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_signed_in_as, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    KNOWN_PASSWORD,
    ROTATED_PASSWORD,
    WEAK_PASSWORD,
    WRONG_PASSWORD,
    ApiErrorPayload,
)
from alma_spei_tests.data import ProvisionedAccount
from alma_spei_tests.steps import auth_steps, donors_steps
from alma_spei_tests.testbase import BaseApiTest


@allure.feature("Password change")
class TestTemporaryPassword(BaseApiTest):
    def test_temporary_password_blocks_donor_access(
        self, anonymous_api: AlmaSpeiApi, staff: ProvisionedAccount
    ):
        # 1. Log in with a temporary password (no rotation)
        # 2. List donors
        # 3. Verification: HTTP 403 password-change-required
        auth_steps.login(anonymous_api, staff.username, staff.temporary_password)
        response = donors_steps.list_donors(anonymous_api)
        assert_error(response, HTTPStatus.FORBIDDEN, ApiErrorPayload.PASSWORD_CHANGE_REQUIRED)

    def test_rotating_the_temporary_password_unlocks_the_account(
        self, anonymous_api: AlmaSpeiApi, staff: ProvisionedAccount
    ):
        # 1. Log in with a temporary password
        # 2. Change it to a policy-valid password
        # 3. List donors with the new session
        # 4. Verification: a fresh session without the change flag, and donors answer 200
        login = auth_steps.login(anonymous_api, staff.username, staff.temporary_password)
        old_token = anonymous_api.session.session_token
        response = auth_steps.change_password(
            anonymous_api, staff.temporary_password, KNOWN_PASSWORD
        )
        donors = donors_steps.list_donors(anonymous_api)
        with soft_assertions():
            assert_status(login, HTTPStatus.OK, "logging in with the temporary password")
            assert_signed_in_as(response, staff.username)
            assert_that(response.json()["user"]["password-change-required"]).described_as(
                "the change flag should be cleared after rotation"
            ).is_false()
            assert_that(anonymous_api.session.session_token).described_as(
                "rotation should issue a new session token"
            ).is_not_equal_to(old_token)
            assert_status(donors, HTTPStatus.OK, "listing donors after rotation")


@allure.feature("Password change")
class TestPasswordChangeRules(BaseApiTest):
    def test_password_change_issues_a_new_session(self, staff_api: AlmaSpeiApi):
        # 1. Change the password of a signed-in staff account
        # 2. Inspect the session
        # 3. Verification: HTTP 200, a new session token, and the session still resolves
        old_token = staff_api.session.session_token
        response = auth_steps.change_password(staff_api, KNOWN_PASSWORD, ROTATED_PASSWORD)
        current = staff_api.current_user()
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "changing the password")
            assert_that(staff_api.session.session_token).described_as(
                "a password change should rotate the session token"
            ).is_not_equal_to(old_token)
            assert_that(current).described_as(
                "the new session should resolve to the user"
            ).is_not_none()

    def test_wrong_current_password_is_rejected(self, staff_api: AlmaSpeiApi):
        # 1. Change the password giving a wrong current password
        # 2. Verification: HTTP 422 invalid-password
        response = auth_steps.change_password(staff_api, WRONG_PASSWORD, ROTATED_PASSWORD)
        assert_error(response, HTTPStatus.UNPROCESSABLE_ENTITY, ApiErrorPayload.INVALID_PASSWORD)

    def test_reusing_the_current_password_is_rejected(self, staff_api: AlmaSpeiApi):
        # 1. Change the password to the same value
        # 2. Verification: HTTP 422 password-reused
        response = auth_steps.change_password(staff_api, KNOWN_PASSWORD, KNOWN_PASSWORD)
        assert_error(response, HTTPStatus.UNPROCESSABLE_ENTITY, ApiErrorPayload.PASSWORD_REUSED)

    def test_new_password_must_satisfy_the_policy(self, staff_api: AlmaSpeiApi):
        # 1. Change the password to one without an uppercase letter or symbol
        # 2. Verification: HTTP 422 validation
        response = auth_steps.change_password(staff_api, KNOWN_PASSWORD, WEAK_PASSWORD)
        assert_error(response, HTTPStatus.UNPROCESSABLE_ENTITY, ApiErrorPayload.AUTH_VALIDATION)
