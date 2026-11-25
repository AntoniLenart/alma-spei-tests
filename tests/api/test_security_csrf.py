"""API security sweep: every mutating route checks the CSRF token and the origin.

A mutation must carry the ``alma-csrf`` cookie, an ``X-CSRF-Token`` header equal
to it and the app's own ``Origin``. Each mutating route of
``alma_spei_tests.routes`` is called by a signed-in administrator with one of
these broken: no token, a forged token, a foreign origin, no origin. Every call
must be refused with 403 ``csrf`` before anything else is looked at.

The sweep uses its own administrator session, so that a logout that slipped
through could not end the session the rest of the suite shares.
"""

from collections.abc import Iterator
from http import HTTPStatus

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import ErrorCode, Header
from alma_spei_tests.db import DbQueries
from alma_spei_tests.http import HeaderOverrides
from alma_spei_tests.routes import MUTATIONS, Route
from alma_spei_tests.testbase import BaseApiTest

#: A request origin that is not the app.
FOREIGN_ORIGIN = "https://attacker.invalid"
#: A token the server never issued.
FORGED_TOKEN = "forged-csrf-token"

#: How each variant breaks the CSRF protection (header overrides; None drops one).
BROKEN: dict[str, HeaderOverrides] = {
    "no-token": {Header.CSRF_TOKEN: None},
    "forged-token": {Header.CSRF_TOKEN: FORGED_TOKEN},
    "foreign-origin": {Header.ORIGIN: FOREIGN_ORIGIN},
    "no-origin": {Header.ORIGIN: None},
}


@allure.feature("Security: CSRF")
class TestCsrfSweep(BaseApiTest):
    @pytest.mark.parametrize("variant", list(BROKEN))
    @pytest.mark.parametrize("route", [pytest.param(r, id=r.id) for r in MUTATIONS])
    def test_a_mutation_without_a_valid_csrf_token_and_origin_is_refused(
        self, csrf_probe_api: AlmaSpeiApi, route: Route, variant: str
    ):
        # 1. As a signed-in administrator, call the mutating route with the token or the
        #    origin broken
        # 2. Verification: 403 csrf
        response = csrf_probe_api.session.request(
            route.method, route.url(), headers=BROKEN[variant], **route.body()
        )
        with soft_assertions():
            assert_that(response.status_code).described_as(
                f"{variant} should be refused (body: {response.text[:200]})"
            ).is_equal_to(HTTPStatus.FORBIDDEN)
            assert_that(response.json().get("code")).described_as(
                "the refusal should name the CSRF check"
            ).is_equal_to(ErrorCode.CSRF)

    def test_the_probe_session_survived_the_sweep(self, csrf_probe_api: AlmaSpeiApi):
        # 1. After the sweep, read the probe session's user
        # 2. Verification: still signed in - no refused logout ended it
        assert_that(csrf_probe_api.current_user()).described_as(
            "no mutation of the sweep should have taken effect"
        ).is_not_none()


# --- file-local fixtures --------------------------------------------------------
@pytest.fixture(scope="module")
def csrf_probe_api(settings: Settings, base_url: str, db: DbQueries) -> Iterator[AlmaSpeiApi]:
    """A second administrator session, used only by this sweep."""
    db.clear_auth_throttle()
    client = AlmaSpeiApi.connect(base_url, timeout=settings.http_timeout_s)
    client.sign_in(settings.admin_username, settings.admin_password)
    yield client
    client.close()
