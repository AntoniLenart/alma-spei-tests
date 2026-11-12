"""API tests for sessions: inspection, login, logout and CSRF/Origin protection.

Every mutation must carry the ``alma-csrf`` cookie, an equal ``X-CSRF-Token``
header and the app ``Origin``; ``AuthSession`` adds them, and the negative
tests below remove or falsify them one at a time.
"""

from collections.abc import Iterator
from http import HTTPStatus

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_signed_in_as, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import (
    LOGIN_ATTEMPTS_PER_USERNAME,
    WRONG_PASSWORD,
    ApiErrorPayload,
    Header,
)
from alma_spei_tests.data import ProvisionedAccount, new_account
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import auth_steps
from alma_spei_tests.testbase import BaseApiTest

#: An Origin that is not the app's own.
FOREIGN_ORIGIN = "http://evil.example"

#: A well-formed username (validation-only tests never reach an account lookup).
SOME_USERNAME = "qa.validation"

#: Shorter than the 3-character username minimum.
TOO_SHORT_USERNAME = "qa"


@allure.feature("Authentication")
class TestSessionInspection(BaseApiTest):
    @pytest.mark.smoke
    def test_anonymous_session_has_no_user_and_issues_csrf_cookie(self, anonymous_api: AlmaSpeiApi):
        # 1. Inspect the session of a fresh, signed-out client
        # 2. Verification: user is null, a CSRF token is returned and matches the alma-csrf cookie
        response = auth_steps.inspect_session(anonymous_api)
        body = response.json()
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "inspecting an anonymous session")
            assert_that(body["user"]).described_as(
                "anonymous session should have no user"
            ).is_none()
            assert_that(body["csrf"]).described_as(
                "returned CSRF token should equal the alma-csrf cookie"
            ).is_equal_to(anonymous_api.session.csrf_token)

    def test_signed_in_session_reports_the_principal(self, api: AlmaSpeiApi, settings: Settings):
        # 1. Inspect the shared admin session
        # 2. Verification: the principal is the active, rotated QA administrator
        user = auth_steps.inspect_session(api).json()["user"]
        assert_principal(user, settings.admin_username, administrator=True)


@allure.feature("Authentication")
class TestLogin(BaseApiTest):
    def test_login_with_temporary_password_requires_a_password_change(
        self, anonymous_api: AlmaSpeiApi, staff: ProvisionedAccount
    ):
        # 1. Log in as a freshly created account with its temporary password
        # 2. Verification: login succeeds, sets alma-session, and flags password-change-required
        response = auth_steps.login(anonymous_api, staff.username, staff.temporary_password)
        with soft_assertions():
            assert_signed_in_as(response, staff.username)
            assert_that(response.json()["user"]["password-change-required"]).described_as(
                "a temporary password should force a password change"
            ).is_true()
            assert_that(anonymous_api.session.session_token).described_as(
                "login should set the alma-session cookie"
            ).is_not_none()

    def test_username_is_case_insensitive(
        self, anonymous_api: AlmaSpeiApi, staff: ProvisionedAccount
    ):
        # 1. Log in with the username in upper case
        # 2. Verification: login succeeds for the canonical (lower-case) account
        response = auth_steps.login(anonymous_api, staff.username.upper(), staff.temporary_password)
        assert_signed_in_as(response, staff.username)

    def test_wrong_password_is_rejected(
        self, anonymous_api: AlmaSpeiApi, staff: ProvisionedAccount
    ):
        # 1. Log in with a wrong password for an existing account
        # 2. Verification: HTTP 401 with the generic invalid-credentials payload, no session cookie
        response = auth_steps.login(anonymous_api, staff.username, WRONG_PASSWORD)
        with soft_assertions():
            assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.INVALID_CREDENTIALS)
            assert_that(anonymous_api.session.session_token).described_as(
                "a failed login should not set alma-session"
            ).is_none()

    def test_unknown_username_gets_the_same_answer_as_a_wrong_password(
        self, anonymous_api: AlmaSpeiApi
    ):
        # 1. Log in with a username that does not exist
        # 2. Verification: the same HTTP 401 invalid-credentials payload (no account enumeration)
        response = auth_steps.login(anonymous_api, new_account().username, WRONG_PASSWORD)
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.INVALID_CREDENTIALS)

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param({"username": SOME_USERNAME}, id="missing-password"),
            pytest.param(
                {"username": TOO_SHORT_USERNAME, "password": WRONG_PASSWORD},
                id="username-too-short",
            ),
            pytest.param(
                {"username": SOME_USERNAME, "password": WRONG_PASSWORD, "admin": True},
                id="unknown-field",
            ),
        ],
    )
    def test_invalid_login_body_is_rejected(self, anonymous_api: AlmaSpeiApi, body: dict):
        # 1. Submit a login body that violates the login contract
        # 2. Verification: HTTP 422 with the generic validation payload
        response = auth_steps.login_with(anonymous_api, body)
        assert_error(response, HTTPStatus.UNPROCESSABLE_ENTITY, ApiErrorPayload.AUTH_VALIDATION)

    @pytest.mark.usefixtures("throttle_cleanup")
    def test_logins_are_throttled_per_username(self, anonymous_api: AlmaSpeiApi):
        # 1. Fail to log in as one unknown username as many times as the limit allows
        # 2. Try once more with the same username
        # 3. Verification: the attempts within the limit get 401, the next one gets 429
        username = new_account().username
        within_limit = [
            auth_steps.login(anonymous_api, username, WRONG_PASSWORD).status_code
            for _ in range(LOGIN_ATTEMPTS_PER_USERNAME)
        ]
        response = auth_steps.login(anonymous_api, username, WRONG_PASSWORD)
        with soft_assertions():
            assert_that(within_limit).described_as(
                "attempts within the limit should all be rejected as invalid credentials"
            ).is_equal_to([HTTPStatus.UNAUTHORIZED] * LOGIN_ATTEMPTS_PER_USERNAME)
            assert_error(response, HTTPStatus.TOO_MANY_REQUESTS, ApiErrorPayload.THROTTLED)


@allure.feature("Authentication")
class TestCsrfProtection(BaseApiTest):
    @pytest.mark.parametrize(
        "headers",
        [
            pytest.param({Header.CSRF_TOKEN: None}, id="no-csrf-header"),
            pytest.param({Header.CSRF_TOKEN: "forged.token.value"}, id="mismatched-csrf-header"),
            pytest.param({Header.ORIGIN: FOREIGN_ORIGIN}, id="foreign-origin"),
            pytest.param({Header.ORIGIN: None}, id="no-origin"),
        ],
    )
    def test_login_without_valid_csrf_or_origin_is_forbidden(
        self, anonymous_api: AlmaSpeiApi, staff: ProvisionedAccount, headers: dict
    ):
        # 1. Log in with correct credentials but one CSRF/Origin requirement broken
        # 2. Verification: HTTP 403 csrf payload and no session is issued
        response = auth_steps.login(
            anonymous_api, staff.username, staff.temporary_password, headers=headers
        )
        with soft_assertions():
            assert_error(response, HTTPStatus.FORBIDDEN, ApiErrorPayload.CSRF)
            assert_that(anonymous_api.session.session_token).described_as(
                "a rejected login should not set alma-session"
            ).is_none()


# --- file-local fixtures and helpers ------------------------------------------
@pytest.fixture
def throttle_cleanup(db: DbQueries) -> Iterator[None]:
    """Reset login throttle buckets after a test that exhausts them on purpose."""
    yield
    db.clear_auth_throttle()


def assert_principal(user: dict, username: str, *, administrator: bool):
    with soft_assertions():
        assert_that(user["username"]).described_as(
            "principal should be the expected account"
        ).is_equal_to(username)
        assert_that(user["administrator"]).described_as(
            "principal administrator flag should match the account"
        ).is_equal_to(administrator)
        assert_that(user["active"]).described_as("principal should be active").is_true()
        assert_that(user["password-change-required"]).described_as(
            "principal should have a rotated password"
        ).is_false()
