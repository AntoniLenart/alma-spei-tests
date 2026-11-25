"""API security tests for response headers and error bodies.

Every response - the UI page and its script, API answers, refusals and "not
found" pages - must carry the protective headers, and an error must explain
itself in Polish without exposing internals (stack traces, class names, file
paths, server versions). A Content-Security-Policy and a framing ban are missing
today; those checks are strict expected failures until the filed bug is fixed.
"""

from http import HTTPStatus
from typing import Any

import allure
import httpx
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import BODY_LIMIT_BYTES, ContentType, Header, SecurityHeaderValue
from alma_spei_tests.testbase import BaseApiTest

#: What the different kinds of response are, and how to get one anonymously.
RESPONSES: dict[str, tuple[str, str, dict[str, Any]]] = {
    "ui-page": ("GET", "/", {}),
    "ui-script": ("GET", "/js/app.js", {}),
    "session-probe": ("GET", "/api/auth/session", {}),
    "health": ("GET", "/api/health/live", {}),
    "api-not-found": ("GET", "/api/qa-no-such-route", {}),
    "page-not-found": ("GET", "/qa-no-such-page.html", {}),
    "unauthenticated": ("GET", "/api/donors", {}),
    "malformed-body": (
        "POST",
        "/api/auth/login",
        {"content": b"{not json", "headers": {Header.CONTENT_TYPE: ContentType.JSON}},
    ),
    "body-too-large": ("POST", "/api/auth/login", {"json": {"x": "y" * (BODY_LIMIT_BYTES + 1)}}),
}
ERRORS = ("api-not-found", "unauthenticated", "malformed-body", "body-too-large")

#: Signs of internals that must never reach a client (searched, case-insensitive).
INTERNALS_PATTERN = (
    r"(?i)Exception|\bat [a-z]+\.[\w.$]+\(|clojure\.|java\.|\.clj\b|/home/|C:\\|stack ?trace"
)

#: The filed bug for the Server header naming Jetty and its version.
SERVER_VERSION_BUG = "every response names the server and its version; filed as a bug"
#: The filed bug for the missing Content-Security-Policy and framing protection.
MISSING_CSP_BUG = "no Content-Security-Policy or framing ban on any response; filed as a bug"


@allure.feature("Security: headers")
class TestSecurityHeaders(BaseApiTest):
    @pytest.mark.parametrize("kind", list(RESPONSES))
    def test_every_kind_of_response_carries_the_protective_headers(
        self, anonymous_api: AlmaSpeiApi, kind: str
    ):
        # 1. Get one response of this kind without a session
        # 2. Verification: no MIME sniffing, no referrer and no caching
        response = fetch(anonymous_api, kind)
        assert_that(protective_headers(response)).described_as(
            f"the {kind} response should carry the protective headers"
        ).is_equal_to(
            {
                Header.CONTENT_TYPE_OPTIONS: SecurityHeaderValue.NOSNIFF,
                Header.REFERRER_POLICY: SecurityHeaderValue.NO_REFERRER,
                Header.CACHE_CONTROL: SecurityHeaderValue.NO_STORE,
            }
        )

    @pytest.mark.xfail(strict=True, reason=SERVER_VERSION_BUG)
    @pytest.mark.parametrize("kind", ["ui-page", "ui-script", "session-probe"])
    def test_no_response_names_the_server_software(self, anonymous_api: AlmaSpeiApi, kind: str):
        # 1. Get one response of this kind
        # 2. Verification: no Server version and no X-Powered-By header
        response = fetch(anonymous_api, kind)
        with soft_assertions():
            assert_that(response.headers.get("server", "")).described_as(
                "the Server header should not disclose a version"
            ).does_not_match(r".*\d")
            assert_that(response.headers.get("x-powered-by")).described_as(
                "no X-Powered-By header should be sent"
            ).is_none()

    @pytest.mark.xfail(strict=True, reason=MISSING_CSP_BUG)
    def test_the_ui_page_restricts_scripts_and_cannot_be_framed(self, anonymous_api: AlmaSpeiApi):
        # 1. Get the UI page
        # 2. Verification: a Content-Security-Policy, and framing forbidden (frame-ancestors
        #    or X-Frame-Options)
        response = fetch(anonymous_api, "ui-page")
        policy = response.headers.get("content-security-policy", "")
        framing = response.headers.get("x-frame-options", "").upper()
        with soft_assertions():
            assert_that(policy).described_as("the page should have a CSP").is_not_empty()
            assert_that(
                "frame-ancestors" in policy or framing in {"DENY", "SAMEORIGIN"}
            ).described_as("the page should not be framable by another site").is_true()


@allure.feature("Security: headers")
class TestErrorBodies(BaseApiTest):
    @pytest.mark.parametrize("kind", ERRORS)
    def test_an_error_explains_itself_without_internals(
        self, anonymous_api: AlmaSpeiApi, kind: str
    ):
        # 1. Provoke one kind of error without a session
        # 2. Verification: a JSON body with only a code and a Polish message, and no stack
        #    trace, class name or path
        response = fetch(anonymous_api, kind)
        body = response.json()
        with soft_assertions():
            assert_that(response.status_code).described_as(
                f"{kind} should be a client error"
            ).is_between(HTTPStatus.BAD_REQUEST, HTTPStatus.INTERNAL_SERVER_ERROR - 1)
            assert_that(set(body)).described_as(
                "an error should carry only its code and message"
            ).is_equal_to({"code", "message"})
            assert_that(response.text).described_as(
                "an error should expose no internals"
            ).does_not_match(INTERNALS_PATTERN)


# --- file-local helpers -------------------------------------------------------
def fetch(client: AlmaSpeiApi, kind: str) -> httpx.Response:
    method, path, options = RESPONSES[kind]
    return client.session.request(method, path, **options)


def protective_headers(response: httpx.Response) -> dict[str, str | None]:
    return {
        name: response.headers.get(name)
        for name in (Header.CONTENT_TYPE_OPTIONS, Header.REFERRER_POLICY, Header.CACHE_CONTROL)
    }
