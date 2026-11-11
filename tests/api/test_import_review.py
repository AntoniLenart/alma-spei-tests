"""API tests for the bank review queue, batch reads and manual comparison (task 37).

Everything here is read-only: browsing the queue or comparing a staged row with
a chosen donor never records a decision or changes review progress.
"""

import uuid
from collections.abc import Callable
from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_error_includes, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    ApiErrorPayload,
    ImportErrorPayload,
    ImportState,
    RowState,
)
from alma_spei_tests.data import (
    BankRow,
    BankStatement,
    DonorFactory,
    blank_only_csv,
    new_donor_profile,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, imports_steps
from alma_spei_tests.testbase import BaseApiTest

#: An impossible date and a malformed amount: invalid, yet comparable.
INVALID_DATE = "2026-02-30"
MALFORMED_AMOUNT = "12.34.56"


@allure.feature("Import review")
class TestReviewQueue(BaseApiTest):
    @pytest.mark.smoke
    def test_newly_staged_batch_heads_the_queue_unreviewed(
        self, api: AlmaSpeiApi, staged_upload: dict[str, Any]
    ):
        # 1. Stage an upload (fixture)
        # 2. Read the first queue entry
        # 3. Verification: it is this batch, awaiting review, with no reviewed rows
        response = imports_steps.review_queue(api, limit=1, offset=0)
        body = response.json()
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "reading the review queue")
            assert_that(
                [(b["id"], b["state"], b["reviewed-rows"]) for b in body["batches"]]
            ).described_as("the newest staged batch should head the queue, unreviewed").is_equal_to(
                [(staged_upload["batch"]["id"], ImportState.REVIEW, 0)]
            )
            assert_that((body["limit"], body["offset"])).described_as(
                "the queue should echo the requested page"
            ).is_equal_to((1, 0))

    def test_failed_batches_are_not_queued(self, api: AlmaSpeiApi, tag: str):
        # 1. Fail an upload (a file without rows)
        # 2. Read the first page of the queue
        # 3. Verification: the failed batch is not in it
        failed_id = imports_steps.upload(api, f"{tag}.csv", blank_only_csv(tag)).json()["batch-id"]
        queued = [b["id"] for b in imports_steps.review_queue(api).json()["batches"]]
        assert_that(queued).described_as("a failed batch should not await review").does_not_contain(
            failed_id
        )

    @pytest.mark.usefixtures("staged_upload")
    def test_page_past_the_end_is_empty(self, api: AlmaSpeiApi):
        # 1. Read the queue total, then a page starting at that total
        # 2. Verification: no batches on that page
        total = imports_steps.review_queue(api).json()["total"]
        body = imports_steps.review_queue(api, offset=total).json()
        assert_that(body["batches"]).described_as("a page past the end should be empty").is_empty()

    @pytest.mark.parametrize(
        "params",
        [
            pytest.param([("limit", "0")], id="limit-zero"),
            pytest.param([("limit", "101")], id="limit-over-max"),
            pytest.param([("offset", "-1")], id="negative-offset"),
            pytest.param([("limit", "1"), ("limit", "2")], id="repeated-limit"),
            pytest.param([("source-type", "tax")], id="source-filter"),
            pytest.param([("order", "id")], id="ordering"),
        ],
    )
    def test_invalid_queue_query_is_rejected(self, api: AlmaSpeiApi, params: list[tuple[str, str]]):
        # 1. Read the queue with an unsupported or out-of-range parameter
        # 2. Verification: 400 import validation
        response = imports_steps.review_queue_with(api, params)
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    def test_anonymous_client_cannot_read_the_queue(self, anonymous_api: AlmaSpeiApi):
        # 1. Read the queue without signing in
        # 2. Verification: 401 unauthenticated
        response = imports_steps.review_queue(anonymous_api)
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)


@allure.feature("Import review")
class TestBatchRead(BaseApiTest):
    def test_batch_is_readable_by_id(self, api: AlmaSpeiApi, staged_upload: dict[str, Any]):
        # 1. Read a staged batch by id
        # 2. Verification: the same batch the upload reported
        response = imports_steps.read_batch(api, staged_upload["batch"]["id"])
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "reading a batch")
            assert_that(response.json()["batch"]).described_as(
                "the batch should equal the one the upload reported"
            ).is_equal_to(staged_upload["batch"])

    def test_failed_batch_is_readable_too(self, api: AlmaSpeiApi, tag: str):
        # 1. Fail an upload
        # 2. Read its batch
        # 3. Verification: 200 with the failed state
        failed_id = imports_steps.upload(api, f"{tag}.csv", blank_only_csv(tag)).json()["batch-id"]
        body = imports_steps.read_batch(api, failed_id).json()
        assert_that(body["batch"]["state"]).described_as(
            "a failed batch should still be readable"
        ).is_equal_to(ImportState.FAILED)

    def test_batch_read_accepts_no_query_parameters(
        self, api: AlmaSpeiApi, staged_upload: dict[str, Any]
    ):
        # 1. Read a batch with a paging parameter
        # 2. Verification: 400 import validation
        response = imports_steps.read_batch(api, staged_upload["batch"]["id"], [("limit", "1")])
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    @pytest.mark.parametrize(
        "batch_id",
        [
            pytest.param(str(uuid.uuid4()), id="unknown-uuid"),
            pytest.param("bad", id="malformed-id"),
        ],
    )
    def test_unknown_batch_is_not_found(self, api: AlmaSpeiApi, batch_id: str):
        # 1. Read a batch that does not exist
        # 2. Verification: 404 import not-found
        response = imports_steps.read_batch(api, batch_id)
        assert_error(response, HTTPStatus.NOT_FOUND, ImportErrorPayload.NOT_FOUND)


@allure.feature("Import review")
class TestManualComparison(BaseApiTest):
    def test_comparison_shows_the_source_row_and_the_chosen_donor(
        self,
        api: AlmaSpeiApi,
        staged_upload: dict[str, Any],
        bank_statement: BankStatement,
        donor: dict[str, Any],
    ):
        # 1. Compare staged row 1 with a chosen donor
        # 2. Verification: 200 with the batch still unreviewed, the source row and exactly
        #    that donor's public profile - no donations, no audit fields
        response = imports_steps.compare(api, staged_upload["batch"]["id"], 1, 1, donor["id"])
        body = response.json()
        with soft_assertions():
            assert_status(response, HTTPStatus.OK, "comparing a row with a donor")
            assert_that(body["donor"]).described_as(
                "the comparison should show the chosen donor's current profile"
            ).is_equal_to(donor)
            assert_that((body["row"]["row-number"], body["row"]["payload"]["sender"])).described_as(
                "the comparison should show the requested source row"
            ).is_equal_to((1, bank_statement.rows[0].sender))
            assert_that(body["batch"]["reviewed-rows"]).described_as(
                "comparing should not count as reviewing"
            ).is_equal_to(0)
            assert_that(sorted(body)).described_as(
                "the comparison should carry only batch, row and donor"
            ).is_equal_to(["batch", "donor", "row"])

    def test_archived_donor_can_be_compared(
        self,
        api: AlmaSpeiApi,
        db: DbQueries,
        staged_upload: dict[str, Any],
        donor_factory: DonorFactory,
        tag: str,
    ):
        # 1. Create a tagged donor and archive it
        # 2. Compare a staged row with it
        # 3. Verification: 200 and the donor is shown as inactive
        archived = donor_factory(new_donor_profile(tag=tag))
        db_steps.archive_donor(db, archived["id"])
        body = imports_steps.compare(api, staged_upload["batch"]["id"], 1, 1, archived["id"]).json()
        assert_that(body["donor"]["is-active"]).described_as(
            "an archived donor should be comparable and shown as inactive"
        ).is_false()

    def test_invalid_row_is_comparable_with_its_errors(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage a statement whose only line is invalid
        # 2. Compare that line with a donor
        # 3. Verification: 200, the row is invalid and keeps its raw source amount
        statement = BankStatement([BankRow(INVALID_DATE, donor["name"], tag, MALFORMED_AMOUNT)])
        batch = imports_steps.upload_staged(api, f"{tag}.csv", statement.to_csv())["batch"]
        row = imports_steps.compare(api, batch["id"], 1, 1, donor["id"]).json()["row"]
        assert_that((row["validation-state"], row["payload"]["source-amount"])).described_as(
            "an invalid row should stay comparable with its source values"
        ).is_equal_to((RowState.INVALID, MALFORMED_AMOUNT))

    @pytest.mark.parametrize(
        ("worksheet", "row"),
        [pytest.param(1, 99, id="no-such-row"), pytest.param(2, 1, id="no-such-sheet")],
    )
    def test_missing_row_is_not_found(
        self,
        api: AlmaSpeiApi,
        staged_upload: dict[str, Any],
        donor: dict[str, Any],
        worksheet: int,
        row: int,
    ):
        # 1. Compare a row locator that does not exist in the batch
        # 2. Verification: 404 row not-found
        response = imports_steps.compare(
            api, staged_upload["batch"]["id"], worksheet, row, donor["id"]
        )
        assert_error(response, HTTPStatus.NOT_FOUND, ImportErrorPayload.ROW_NOT_FOUND)

    def test_unknown_donor_is_not_found(self, api: AlmaSpeiApi, staged_upload: dict[str, Any]):
        # 1. Compare a staged row with a donor id that does not exist
        # 2. Verification: 404 donor not-found
        response = imports_steps.compare(api, staged_upload["batch"]["id"], 1, 1, str(uuid.uuid4()))
        assert_error(response, HTTPStatus.NOT_FOUND, ApiErrorPayload.DONOR_NOT_FOUND)

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param(lambda d: [], id="no-donor-id"),
            pytest.param(lambda d: [("donor-id", "bad")], id="malformed-donor-id"),
            pytest.param(lambda d: [("donor-id", d), ("extra", "x")], id="extra-parameter"),
            pytest.param(lambda d: [("donor-id", d), ("donor-id", d)], id="repeated-donor-id"),
        ],
    )
    def test_invalid_comparison_query_is_rejected(
        self,
        api: AlmaSpeiApi,
        staged_upload: dict[str, Any],
        donor: dict[str, Any],
        query: Callable[[str], list[tuple[str, str]]],
    ):
        # 1. Compare a staged row with a missing, malformed, extra or repeated donor parameter
        # 2. Verification: 400 import validation
        response = imports_steps.compare(
            api, staged_upload["batch"]["id"], 1, 1, params=query(donor["id"])
        )
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    def test_malformed_row_locator_is_rejected(
        self, api: AlmaSpeiApi, staged_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Compare with a non-numeric worksheet in the path
        # 2. Verification: 400 import validation
        response = imports_steps.compare(api, staged_upload["batch"]["id"], "bad", 1, donor["id"])
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)

    def test_batch_not_awaiting_review_cannot_be_compared(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Fail an upload
        # 2. Compare "row 1" of that batch with a donor
        # 3. Verification: 409 review-unavailable
        failed_id = imports_steps.upload(api, f"{tag}.csv", blank_only_csv(tag)).json()["batch-id"]
        response = imports_steps.compare(api, failed_id, 1, 1, donor["id"])
        assert_error(response, HTTPStatus.CONFLICT, ImportErrorPayload.REVIEW_UNAVAILABLE)

    def test_anonymous_client_cannot_compare(
        self, anonymous_api: AlmaSpeiApi, staged_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Compare without signing in
        # 2. Verification: 401 unauthenticated
        response = imports_steps.compare(
            anonymous_api, staged_upload["batch"]["id"], 1, 1, donor["id"]
        )
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)
