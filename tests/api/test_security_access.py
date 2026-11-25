"""API security sweeps: who may call which route.

Every route in ``alma_spei_tests.routes`` is called, with a valid CSRF token and
origin so that only the access rule decides:

* without a session, every protected route answers 401;
* with a temporary password, everything but the session probe, the password
  change and logout answers 403 until the password is changed;
* a staff member without account management answers 403 on account routes.

Ids in the paths exist nowhere, so nothing changes even if a check were missing.
"""

from collections.abc import Iterator
from http import HTTPStatus

import allure
import httpx
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi, expect_status
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import KNOWN_PASSWORD, ContentType, ErrorCode, Header
from alma_spei_tests.data import ProvisionedAccount, new_account
from alma_spei_tests.db import DbQueries
from alma_spei_tests.routes import (
    ADMIN_ONLY,
    BLOCKED_BY_TEMPORARY_PASSWORD,
    PROTECTED,
    Route,
)
from alma_spei_tests.steps import auth_steps
from alma_spei_tests.testbase import BaseApiTest

#: Routes that validate the request body before checking the session (filed bug): an
#: anonymous or temporary-password client gets 400/422 with field names instead.
VALIDATED_BEFORE_AUTH = {
    "POST /api/auth/password",
    "POST /api/imports/commit",
    "POST /api/imports/undo-last",
    "POST /api/imports/{id}/previews/{preview}/backup",
}
VALIDATED_BEFORE_AUTH_BUG = "the body is validated before the session is checked; filed as a bug"


def route_params(routes: tuple[Route, ...]) -> list:
    """The routes as parameters; one with the filed bug is a strict expected failure."""
    return [
        pytest.param(
            route,
            id=route.id,
            marks=[pytest.mark.xfail(strict=True, reason=VALIDATED_BEFORE_AUTH_BUG)]
            if route.id in VALIDATED_BEFORE_AUTH
            else [],
        )
        for route in routes
    ]


@allure.feature("Security: access")
class TestAnonymousAccess(BaseApiTest):
    @pytest.mark.parametrize("route", route_params(PROTECTED))
    def test_a_protected_route_refuses_an_anonymous_client(
        self, anonymous_api: AlmaSpeiApi, route: Route
    ):
        # 1. Call the route without a session (with a valid CSRF token and origin)
        # 2. Verification: 401 unauthenticated
        response = call(anonymous_api, route)
        assert_refused(response, HTTPStatus.UNAUTHORIZED, ErrorCode.UNAUTHENTICATED)


@allure.feature("Security: access")
class TestTemporaryPassword(BaseApiTest):
    @pytest.mark.parametrize("route", route_params(BLOCKED_BY_TEMPORARY_PASSWORD))
    def test_a_temporary_password_blocks_the_rest_of_the_api(
        self, temporary_api: AlmaSpeiApi, route: Route
    ):
        # 1. Sign in with a temporary password, without changing it (fixture)
        # 2. Call the route
        # 3. Verification: 403 password change required
        response = call(temporary_api, route)
        assert_refused(response, HTTPStatus.FORBIDDEN, ErrorCode.PASSWORD_CHANGE_REQUIRED)


@allure.feature("Security: access")
class TestAccountManagementRights(BaseApiTest):
    @pytest.mark.parametrize("route", route_params(ADMIN_ONLY))
    def test_staff_cannot_manage_accounts(self, staff_session: AlmaSpeiApi, route: Route):
        # 1. Call the account route as a staff member without account management
        # 2. Verification: 403 forbidden
        response = call(staff_session, route)
        assert_refused(response, HTTPStatus.FORBIDDEN, ErrorCode.FORBIDDEN)


# --- file-local fixtures and helpers ------------------------------------------
@pytest.fixture(scope="module")
def module_accounts(api: AlmaSpeiApi, db: DbQueries) -> Iterator[list[ProvisionedAccount]]:
    """Staff accounts created for this module, deactivated afterwards.

    The sessions below are module-scoped: logins are throttled per client
    address, and one login per role is enough for the whole sweep.
    """
    db.clear_auth_throttle()
    created: list[ProvisionedAccount] = []
    yield created
    for account in created:
        auth_steps.deactivate_account(api, account.id, account.display_name)


@pytest.fixture(scope="module")
def temporary_api(
    api: AlmaSpeiApi, module_accounts: list[ProvisionedAccount], settings: Settings, base_url: str
) -> Iterator[AlmaSpeiApi]:
    """A staff account signed in with its temporary password, never changed."""
    account = auth_steps.create_account(api, new_account())
    module_accounts.append(account)
    client = AlmaSpeiApi.connect(base_url, timeout=settings.http_timeout_s)
    expect_status(
        auth_steps.login(client, account.username, account.temporary_password),
        HTTPStatus.OK,
        "Sign in with the temporary password",
    )
    yield client
    client.close()


@pytest.fixture(scope="module")
def staff_session(
    api: AlmaSpeiApi, module_accounts: list[ProvisionedAccount], settings: Settings, base_url: str
) -> Iterator[AlmaSpeiApi]:
    """A staff account (no account management) with its password changed."""
    account = auth_steps.create_account(api, new_account())
    module_accounts.append(account)
    client = AlmaSpeiApi.connect(base_url, timeout=settings.http_timeout_s)
    client.sign_in(account.username, account.temporary_password, new_password=KNOWN_PASSWORD)
    yield client
    client.close()


def call(client: AlmaSpeiApi, route: Route) -> httpx.Response:
    return client.session.request(route.method, route.url(), **route.body())


def assert_refused(response: httpx.Response, status: HTTPStatus, code: str):
    is_json = response.headers.get(Header.CONTENT_TYPE, "").startswith(ContentType.JSON)
    body = response.json() if is_json else {}
    with soft_assertions():
        assert_that(response.status_code).described_as(
            f"the route should be refused with {status} (body: {response.text[:200]})"
        ).is_equal_to(status)
        assert_that(body.get("code")).described_as(
            "the refusal should name its reason"
        ).is_equal_to(code)
