"""Shared assertion helpers.

Tests do not chain ``assert_that(...)`` for common checks; they call a named
helper from here. Helpers that make more than one assertion use a
``soft_assertions`` block so every failure is reported at once. Descriptions
read as expectations ("... should ...").
"""

from http import HTTPStatus

import httpx
from assertpy import assert_that, soft_assertions

from alma_spei_tests.constants import (
    HEALTH_STATUS_VALUES,
    ApiErrorPayload,
    ContentType,
    HealthStatus,
)
from alma_spei_tests.contracts import validate_health_response


def assert_health_ok(response: httpx.Response):
    """A health endpoint returned HTTP 200 with body ``{"status": "ok"}``."""
    with soft_assertions():
        assert_that(response.status_code).described_as(
            "health endpoint should return HTTP 200"
        ).is_equal_to(HTTPStatus.OK)
        assert_that(response.json()).described_as(
            "health body should report status ok"
        ).is_equal_to({"status": HealthStatus.OK})


def assert_json_content_type(response: httpx.Response):
    """The response is served as JSON."""
    assert_that(response.headers.get("content-type", "")).described_as(
        "response should be served as JSON"
    ).contains(ContentType.JSON)


def assert_not_found(response: httpx.Response):
    """An unknown API route returned the Polish JSON 404 payload."""
    with soft_assertions():
        assert_that(response.status_code).described_as(
            "unknown API route should return HTTP 404"
        ).is_equal_to(HTTPStatus.NOT_FOUND)
        assert_that(response.headers.get("content-type", "")).described_as(
            "error response should be served as JSON"
        ).contains(ContentType.JSON)
        assert_that(response.json()).described_as(
            "not-found payload should match the Polish contract"
        ).is_equal_to(ApiErrorPayload.NOT_FOUND)


def assert_matches_health_contract(body: object):
    """The body satisfies the shared Malli health contract (no violations)."""
    violations = validate_health_response(body)
    assert_that(violations).described_as(
        "health response should satisfy the shared Malli contract"
    ).is_empty()


def assert_valid_health_status(status: object):
    """The status value is one of the allowed health statuses."""
    assert_that(status).described_as(
        "status should be a valid health status value"
    ).is_in(*HEALTH_STATUS_VALUES)
