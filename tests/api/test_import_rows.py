"""API tests for the staged-row report and for retrying a failed import (task 35)."""

import uuid
from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_error_includes, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    IMPORT_PAGE_DEFAULT_LIMIT,
    IMPORT_PAGE_MAX_LIMIT,
    STAGED_BATCH_VERSION,
    ApiErrorPayload,
    ErrorCode,
    ImportErrorPayload,
    ImportState,
)
from alma_spei_tests.data import BankStatement, blank_only_csv
from alma_spei_tests.steps import imports_steps
from alma_spei_tests.testbase import BaseApiTest


@allure.feature("Bank import")
class TestStagedRowReport(BaseApiTest):
    def test_report_defaults_to_the_first_page(
        self, api: AlmaSpeiApi, staged_upload: dict[str, Any]
    ):
        # 1. Read the staged rows of an upload without paging parameters
        # 2. Verification: the default limit and offset, every row, and the full total
        batch_id = staged_upload["batch"]["id"]
        body = imports_steps.read_rows(api, batch_id).json()
        with soft_assertions():
            assert_that((body["limit"], body["offset"], body["total"])).described_as(
                "the report should default to the first page and count every row"
            ).is_equal_to((IMPORT_PAGE_DEFAULT_LIMIT, 0, len(staged_upload["rows"])))
            assert_that(body["rows"]).described_as(
                "the report should repeat the rows returned by the upload"
            ).is_equal_to(staged_upload["rows"])

    def test_report_is_paginated(self, api: AlmaSpeiApi, staged_upload: dict[str, Any]):
        # 1. Read the second row alone, then a page past the end
        # 2. Verification: one row (row 2) on the second page, none past the end
        batch_id = staged_upload["batch"]["id"]
        second = imports_steps.read_rows(api, batch_id, limit=1, offset=1).json()
        beyond = imports_steps.read_rows(api, batch_id, offset=100).json()
        with soft_assertions():
            assert_that([r["row-number"] for r in second["rows"]]).described_as(
                "the second one-row page should hold row 2"
            ).is_equal_to([2])
            assert_that(beyond["rows"]).described_as(
                "a page past the end should be empty"
            ).is_empty()

    @pytest.mark.parametrize(
        "params",
        [
            pytest.param([("limit", str(IMPORT_PAGE_MAX_LIMIT + 1))], id="limit-over-max"),
            pytest.param([("limit", "0")], id="limit-zero"),
            pytest.param([("offset", "-1")], id="negative-offset"),
            pytest.param([("limit", "1"), ("limit", "2")], id="repeated-limit"),
            pytest.param([("unknown", "true")], id="unknown-parameter"),
        ],
    )
    def test_invalid_page_query_is_rejected(
        self, api: AlmaSpeiApi, staged_upload: dict[str, Any], params: list[tuple[str, str]]
    ):
        # 1. Read the staged rows with an invalid paging parameter
        # 2. Verification: 400 import validation
        response = imports_steps.read_rows_with(api, staged_upload["batch"]["id"], params)
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    @pytest.mark.parametrize(
        "batch_id",
        [
            pytest.param(str(uuid.uuid4()), id="unknown-uuid"),
            pytest.param("not-a-uuid", id="malformed-id"),
        ],
    )
    def test_unknown_batch_is_not_found(self, api: AlmaSpeiApi, batch_id: str):
        # 1. Read the staged rows of a batch that does not exist
        # 2. Verification: 404 import not-found
        response = imports_steps.read_rows(api, batch_id)
        assert_error(response, HTTPStatus.NOT_FOUND, ImportErrorPayload.NOT_FOUND)

    def test_anonymous_client_cannot_read_the_report(
        self, anonymous_api: AlmaSpeiApi, staged_upload: dict[str, Any]
    ):
        # 1. Read an existing batch's rows without signing in
        # 2. Verification: 401 unauthenticated
        response = imports_steps.read_rows(anonymous_api, staged_upload["batch"]["id"])
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)


@allure.feature("Bank import")
class TestRetry(BaseApiTest):
    def test_retry_with_the_original_bytes_creates_the_next_attempt(
        self, api: AlmaSpeiApi, failed_upload: dict[str, Any], tag: str
    ):
        # 1. Fail an upload (a file without rows)
        # 2. Retry it with the same bytes under another name
        # 3. Verification: attempt 2 of the same file, linked to attempt 1, keeping the
        #    original file name (it fails again - the bytes are still without rows)
        first = failed_upload["batch"]
        response = imports_steps.retry(
            api, first["id"], first["version"], f"{tag}-again.csv", failed_upload["content"]
        )
        second = response.json().get("batch", {})
        with soft_assertions():
            assert_error_includes(
                response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.INVALID_STRUCTURE
            )
            assert_that(project(second, RETRY_FIELDS)).described_as(
                "the retry should be the next attempt of the same file"
            ).is_equal_to(
                {
                    "file-id": first["file-id"],
                    "attempt-number": first["attempt-number"] + 1,
                    "retry-of": first["id"],
                    "original-filename": first["original-filename"],
                    "state": ImportState.FAILED,
                }
            )

    def test_retry_requires_the_original_bytes(
        self,
        api: AlmaSpeiApi,
        failed_upload: dict[str, Any],
        bank_statement: BankStatement,
        tag: str,
    ):
        # 1. Fail an upload
        # 2. Retry it with different bytes
        # 3. Verification: 409 retry-file-mismatch
        first = failed_upload["batch"]
        response = imports_steps.retry(
            api, first["id"], first["version"], f"{tag}.csv", bank_statement.to_csv()
        )
        assert_error_includes(response, HTTPStatus.CONFLICT, ImportErrorPayload.RETRY_FILE_MISMATCH)

    def test_retry_with_a_stale_version_is_rejected(
        self, api: AlmaSpeiApi, failed_upload: dict[str, Any], tag: str
    ):
        # 1. Fail an upload
        # 2. Retry it quoting an outdated batch version
        # 3. Verification: 409 stale-import
        first = failed_upload["batch"]
        response = imports_steps.retry(
            api, first["id"], first["version"] - 1, f"{tag}.csv", failed_upload["content"]
        )
        assert_error_includes(response, HTTPStatus.CONFLICT, ImportErrorPayload.STALE_IMPORT)

    def test_only_a_failed_batch_can_be_retried(
        self,
        api: AlmaSpeiApi,
        staged_upload: dict[str, Any],
        bank_statement: BankStatement,
        tag: str,
    ):
        # 1. Stage an upload successfully
        # 2. Retry it with its own bytes
        # 3. Verification: 409 ineligible-retry
        batch = staged_upload["batch"]
        response = imports_steps.retry(
            api, batch["id"], STAGED_BATCH_VERSION, f"{tag}.csv", bank_statement.to_csv()
        )
        assert_error_includes(response, HTTPStatus.CONFLICT, ImportErrorPayload.INELIGIBLE_RETRY)


# --- file-local fixtures and helpers ------------------------------------------
#: Batch fields compared by the retry test.
RETRY_FIELDS = ("file-id", "attempt-number", "retry-of", "original-filename", "state")


@pytest.fixture
def failed_upload(api: AlmaSpeiApi, tag: str) -> dict[str, Any]:
    """A failed first attempt (a file without rows) plus the bytes that were sent."""
    content = blank_only_csv(tag)
    response = imports_steps.upload(api, f"{tag}.csv", content)
    assert_status(response, HTTPStatus.BAD_REQUEST, "uploading a file without rows")
    body = response.json()
    assert_that(body.get("code")).described_as(
        "the setup upload should fail as invalid-structure"
    ).is_equal_to(ErrorCode.INVALID_STRUCTURE)
    return {"batch": body["batch"], "content": content}


def project(mapping: dict, fields: tuple[str, ...]) -> dict:
    return {field: mapping.get(field) for field in fields}
