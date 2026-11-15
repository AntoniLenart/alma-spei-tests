"""Shared assertion helpers.

Tests do not chain ``assert_that(...)`` for common checks; they call a named
helper from here. Helpers that make more than one assertion use a
``soft_assertions`` block so every failure is reported at once. Descriptions
read as expectations ("... should ...").
"""

from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

import httpx
from assertpy import assert_that, soft_assertions

from alma_spei_tests.constants import (
    HEALTH_STATUS_VALUES,
    ApiErrorPayload,
    ContentType,
    ErrorCode,
    Header,
    HealthStatus,
    SecurityHeaderValue,
)
from alma_spei_tests.contracts import Schema


# --- generic HTTP -------------------------------------------------------------
def assert_status(response: httpx.Response, expected: HTTPStatus, what: str):
    """``what`` names the call, e.g. ``"creating a donor"``."""
    assert_that(response.status_code).described_as(
        f"{what} should return HTTP {expected.value} {expected.phrase}"
        f" (body: {response.text[:300]})"
    ).is_equal_to(expected)


def assert_json_content_type(response: httpx.Response):
    """The response is served as JSON."""
    assert_that(response.headers.get(Header.CONTENT_TYPE, "")).described_as(
        "response should be served as JSON"
    ).contains(ContentType.JSON)


def assert_error(response: httpx.Response, expected: HTTPStatus, payload: Mapping[str, str]):
    """An error response with the exact ``{code, message}`` Polish payload."""
    with soft_assertions():
        assert_that(response.status_code).described_as(
            f"error response should have HTTP {expected.value} {expected.phrase}"
        ).is_equal_to(expected)
        assert_that(response.json()).described_as(
            f"error body should be the {payload['code']} payload"
        ).is_equal_to(dict(payload))


def assert_error_includes(
    response: httpx.Response, expected: HTTPStatus, payload: Mapping[str, str]
):
    """Like ``assert_error``, but the body may carry more keys (e.g. batch-id)."""
    body = response.json()
    with soft_assertions():
        assert_that(response.status_code).described_as(
            f"error response should have HTTP {expected.value} {expected.phrase}"
        ).is_equal_to(expected)
        assert_that({key: body.get(key) for key in payload}).described_as(
            f"error body should carry the {payload['code']} code and message"
        ).is_equal_to(dict(payload))


def assert_not_found(response: httpx.Response):
    """An unknown API route returned the Polish JSON 404 payload."""
    with soft_assertions():
        assert_json_content_type(response)
        assert_error(response, HTTPStatus.NOT_FOUND, ApiErrorPayload.NOT_FOUND)


def assert_security_headers(response: httpx.Response):
    """Responses are never cached and carry the hardening headers."""
    expected = {
        Header.CACHE_CONTROL: SecurityHeaderValue.NO_STORE,
        Header.CONTENT_TYPE_OPTIONS: SecurityHeaderValue.NOSNIFF,
        Header.REFERRER_POLICY: SecurityHeaderValue.NO_REFERRER,
    }
    with soft_assertions():
        for header, value in expected.items():
            assert_that(response.headers.get(header)).described_as(
                f"{header} header should be {value}"
            ).is_equal_to(value)


def assert_matches_contract(body: object, schema: Schema, name: str):
    """The body satisfies the Python mirror of the app's Malli contract."""
    assert_that(schema.explain(body)).described_as(
        f"response should satisfy the {name} contract"
    ).is_empty()


# --- health -------------------------------------------------------------------
def assert_health_ok(response: httpx.Response):
    """A health endpoint returned HTTP 200 with body ``{"status": "ok"}``."""
    with soft_assertions():
        assert_that(response.status_code).described_as(
            "health endpoint should return HTTP 200"
        ).is_equal_to(HTTPStatus.OK)
        assert_that(response.json()).described_as(
            "health body should report status ok"
        ).is_equal_to({"status": HealthStatus.OK})


def assert_valid_health_status(status: object):
    """The status value is one of the allowed health statuses."""
    assert_that(status).described_as("status should be a valid health status value").is_in(
        *HEALTH_STATUS_VALUES
    )


# --- auth ---------------------------------------------------------------------
def assert_signed_in_as(response: httpx.Response, username: str):
    """A session-issuing call succeeded for the given (canonical) username."""
    with soft_assertions():
        assert_that(response.status_code).described_as(
            "session-issuing call should return HTTP 200"
        ).is_equal_to(HTTPStatus.OK)
        assert_that(response.json().get("user", {}).get("username")).described_as(
            "session should belong to the signed-in account"
        ).is_equal_to(username)


# --- donors -------------------------------------------------------------------
def assert_donor_matches_profile(donor: Mapping[str, object], payload: Mapping[str, object]):
    """Every profile field of a returned donor equals the submitted payload."""
    with soft_assertions():
        for field, value in payload.items():
            assert_that(donor.get(field)).described_as(
                f"donor {field} should equal the submitted value"
            ).is_equal_to(value)


def assert_donor_validation_error(response: httpx.Response, field: str, code: str):
    """A donor write was rejected with a per-field validation error.

    ``field`` is the kebab-case field name; for unknown-field errors the backend
    reports an empty field path, so pass ``""``.
    """
    body = response.json()
    expected_path = [field] if field else []
    with soft_assertions():
        assert_that(response.status_code).described_as(
            "invalid donor data should be rejected with HTTP 400"
        ).is_equal_to(HTTPStatus.BAD_REQUEST)
        assert_that(body.get("code")).described_as(
            "rejection should carry the validation code"
        ).is_equal_to(ErrorCode.VALIDATION)
        assert_that([(e.get("field"), e.get("code")) for e in body.get("errors", [])]).described_as(
            f"errors should flag {field or 'an unknown field'} as {code}"
        ).contains((expected_path, code))


def assert_ids(donors: Sequence[Mapping[str, Any]], expected: list[str], what: str):
    """The listed donors are exactly ``expected``, in order."""
    assert_that([d["id"] for d in donors]).described_as(
        f"{what} should list exactly the expected donors in order"
    ).is_equal_to(expected)
