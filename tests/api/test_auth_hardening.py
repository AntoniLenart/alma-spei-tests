"""API tests for the authentication foundation's hardening (task 57).

Sessions are random server-side identifiers that end after 30 minutes without
activity or 8 hours after they began; the cookies are HttpOnly and
SameSite=Strict (Secure is switched on outside loopback HTTP, i.e. once TLS is
deployed); every auth and account response is ``no-store``; and accounts are
only ever created by an administrator - there is no self-registration.

Expiry is checked by moving the session back in time in the database (the app
role may update sessions), so no test waits. These tests log in a few times, so
each starts with fresh login throttle buckets.
"""

import re
from collections.abc import Callable, Iterator
from http import HTTPStatus

import allure
import httpx
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_not_found, assert_security_headers
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    KNOWN_PASSWORD,
    ROTATED_PASSWORD,
    SESSION_IDLE_MINUTES,
    SESSION_TOKEN_LENGTH,
    WRONG_PASSWORD,
    ApiErrorPayload,
    Cookie,
    Header,
)
from alma_spei_tests.data import ProvisionedAccount, new_account
from alma_spei_tests.db import DbQueries
from alma_spei_tests.http import set_cookies
from alma_spei_tests.steps import auth_steps, db_steps, donors_steps
from alma_spei_tests.testbase import BaseApiTest

#: base64url without padding: what 32 random bytes encode to.
TOKEN_PATTERN = re.compile(rf"[A-Za-z0-9_-]{{{SESSION_TOKEN_LENGTH}}}")

#: Routes a self-registration feature might use; none may exist.
REGISTRATION_PATHS = ("/api/auth/register", "/api/auth/signup", "/api/register")

#: The SameSite value both cookies carry.
SAME_SITE_STRICT = "Strict"


@pytest.fixture(autouse=True)
def fresh_login_budget(db: DbQueries) -> Iterator[None]:
    """Each test here logs in; start it with empty login throttle buckets."""
    db.clear_auth_throttle()
    yield


@allure.feature("Authentication hardening")
class TestSessionCookies(BaseApiTest):
    def test_the_session_cookie_is_httponly_and_strict(
        self, anonymous_api: AlmaSpeiApi, staff: ProvisionedAccount
    ):
        # 1. Log in
        # 2. Read the Set-Cookie headers of the response
        # 3. Verification: alma-session is a session cookie (no Max-Age/Expires) on Path=/,
        #    HttpOnly and SameSite=Strict; alma-csrf is HttpOnly and SameSite=Strict too
        response = auth_steps.login(anonymous_api, staff.username, staff.temporary_password)
        cookies = set_cookies(response)
        session, csrf = cookies[Cookie.SESSION], cookies[Cookie.CSRF]
        with soft_assertions():
            assert_that((session["httponly"], session["samesite"], session["path"])).described_as(
                "the session cookie should be HttpOnly, Strict and site-wide"
            ).is_equal_to((True, SAME_SITE_STRICT, "/"))
            assert_that((session["max-age"], session["expires"])).described_as(
                "the session cookie should end with the browser session"
            ).is_equal_to(("", ""))
            assert_that((csrf["httponly"], csrf["samesite"])).described_as(
                "the CSRF cookie should be HttpOnly and Strict"
            ).is_equal_to((True, SAME_SITE_STRICT))

    def test_the_secure_flag_waits_for_tls(
        self, anonymous_api: AlmaSpeiApi, staff: ProvisionedAccount
    ):
        # 1. Log in over the loopback HTTP the test stack uses
        # 2. Verification: no Secure flag yet - the app sets it outside loopback HTTP, so the
        #    production check waits for the TLS deployment
        response = auth_steps.login(anonymous_api, staff.username, staff.temporary_password)
        assert_that(set_cookies(response)[Cookie.SESSION]["secure"]).described_as(
            "on loopback HTTP the session cookie should not claim Secure"
        ).is_false()

    def test_every_login_gets_a_new_random_token(
        self, anonymous_api: AlmaSpeiApi, staff: ProvisionedAccount
    ):
        # 1. Log in twice with the same account
        # 2. Verification: two different tokens of 32 random bytes (43 base64url characters)
        tokens = [
            set_cookies(auth_steps.login(anonymous_api, staff.username, staff.temporary_password))[
                Cookie.SESSION
            ].value
            for _ in range(2)
        ]
        with soft_assertions():
            assert_that(tokens[0]).described_as(
                "each login should get a new token"
            ).is_not_equal_to(tokens[1])
            for token in tokens:
                assert_that(bool(TOKEN_PATTERN.fullmatch(token))).described_as(
                    f"token {token[:4]}... should be 43 base64url characters"
                ).is_true()

    def test_logout_clears_the_session_cookie(self, staff_api: AlmaSpeiApi):
        # 1. Log out a signed-in session
        # 2. Verification: alma-session is overwritten with an empty value and Max-Age=0
        session = set_cookies(auth_steps.logout(staff_api))[Cookie.SESSION]
        assert_that((session.value, session["max-age"])).described_as(
            "logout should clear the session cookie"
        ).is_equal_to(("", "0"))


@allure.feature("Authentication hardening")
class TestSessionExpiry(BaseApiTest):
    def test_a_session_survives_just_under_the_idle_limit(
        self, staff_api: AlmaSpeiApi, staff: ProvisionedAccount, db: DbQueries
    ):
        # 1. Make the staff session idle for one minute less than the limit
        # 2. Verification: the session still resolves to the account
        db_steps.age_sessions(db, staff.id, idle_minutes=SESSION_IDLE_MINUTES - 1)
        user = staff_api.current_user()
        assert_that(user and user["username"]).described_as(
            "a session within the idle limit should stay valid"
        ).is_equal_to(staff.username)

    def test_an_idle_session_ends(
        self, staff_api: AlmaSpeiApi, staff: ProvisionedAccount, db: DbQueries
    ):
        # 1. Make the staff session idle for one minute more than the limit
        # 2. Verification: no principal any more, and protected endpoints answer 401
        db_steps.age_sessions(db, staff.id, idle_minutes=SESSION_IDLE_MINUTES + 1)
        assert_session_ended(staff_api)

    def test_a_session_past_its_lifetime_ends(
        self, staff_api: AlmaSpeiApi, staff: ProvisionedAccount, db: DbQueries
    ):
        # 1. Move the staff session past its absolute expiry (still recently active)
        # 2. Verification: no principal any more, and protected endpoints answer 401
        db_steps.age_sessions(db, staff.id, expired=True)
        assert_session_ended(staff_api)


@allure.feature("Authentication hardening")
class TestNoSelfRegistration(BaseApiTest):
    def test_an_anonymous_client_cannot_create_an_account(self, anonymous_api: AlmaSpeiApi):
        # 1. Create an account without signing in
        # 2. Verification: 401 unauthenticated
        response = auth_steps.request_account(anonymous_api, new_account())
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)

    def test_staff_cannot_create_an_account(self, staff_api: AlmaSpeiApi):
        # 1. Create an account as a signed-in staff member (not an administrator)
        # 2. Verification: 403 forbidden
        response = auth_steps.request_account(staff_api, new_account())
        assert_error(response, HTTPStatus.FORBIDDEN, ApiErrorPayload.FORBIDDEN)

    @pytest.mark.parametrize("path", REGISTRATION_PATHS)
    def test_there_is_no_registration_route(self, anonymous_api: AlmaSpeiApi, path: str):
        # 1. POST a registration-like body to a registration-like route
        # 2. Verification: the Polish JSON 404 - the route does not exist
        body = {"username": "qa.self.signup", "password": KNOWN_PASSWORD}
        assert_not_found(auth_steps.post_path(anonymous_api, path, body))


@allure.feature("Authentication hardening")
class TestResponseHeaders(BaseApiTest):
    @pytest.mark.parametrize(
        "call",
        [
            pytest.param(lambda api, anon: auth_steps.inspect_session(anon), id="session"),
            pytest.param(
                lambda api, anon: auth_steps.login(anon, "qa.nobody", WRONG_PASSWORD),
                id="failed-login",
            ),
            pytest.param(lambda api, anon: auth_steps.list_accounts(api), id="accounts"),
            pytest.param(
                lambda api, anon: auth_steps.change_password(api, WRONG_PASSWORD, ROTATED_PASSWORD),
                id="refused-password-change",
            ),
        ],
    )
    def test_auth_and_account_responses_are_never_cached(
        self,
        api: AlmaSpeiApi,
        anonymous_api: AlmaSpeiApi,
        call: Callable[[AlmaSpeiApi, AlmaSpeiApi], httpx.Response],
    ):
        # 1. Call an authentication or account endpoint
        # 2. Verification: Cache-Control no-store and the other hardening headers
        assert_security_headers(call(api, anonymous_api))


@allure.feature("Authentication hardening")
class TestAccountCsrf(BaseApiTest):
    @pytest.mark.parametrize(
        "mutation",
        [
            pytest.param(
                lambda api, staff, headers: auth_steps.request_account_with(
                    api, new_account(), headers
                ),
                id="create-account",
            ),
            pytest.param(
                lambda api, staff, headers: auth_steps.edit_account_with(
                    api, staff.id, staff.display_name, headers
                ),
                id="edit-account",
            ),
            pytest.param(
                lambda api, staff, headers: auth_steps.reset_password_with(api, staff.id, headers),
                id="reset-password",
            ),
        ],
    )
    def test_account_management_without_csrf_is_forbidden(
        self,
        api: AlmaSpeiApi,
        staff: ProvisionedAccount,
        mutation: Callable[..., httpx.Response],
    ):
        # 1. Send an account-management request from the admin session without X-CSRF-Token
        # 2. Verification: 403 csrf
        response = mutation(api, staff, {Header.CSRF_TOKEN: None})
        assert_error(response, HTTPStatus.FORBIDDEN, ApiErrorPayload.CSRF)

    def test_a_password_change_without_csrf_is_forbidden(
        self, staff_api: AlmaSpeiApi, staff: ProvisionedAccount
    ):
        # 1. Change the staff password without X-CSRF-Token
        # 2. Verification: 403 csrf
        response = auth_steps.change_password_with(
            staff_api, KNOWN_PASSWORD, ROTATED_PASSWORD, {Header.CSRF_TOKEN: None}
        )
        assert_error(response, HTTPStatus.FORBIDDEN, ApiErrorPayload.CSRF)


# --- file-local helpers -------------------------------------------------------
def assert_session_ended(api: AlmaSpeiApi):
    """The session resolves to nobody and a protected endpoint refuses it."""
    with soft_assertions():
        assert_that(api.current_user()).described_as(
            "an expired session should not resolve to the account"
        ).is_none()
        assert_error(
            donors_steps.list_donors(api), HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED
        )
