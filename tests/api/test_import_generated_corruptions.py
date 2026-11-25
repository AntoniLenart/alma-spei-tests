"""Generated corrupt bank files and the invariants every one of them must keep.

``data.corrupt.generated_corruptions`` damages valid statements at random from a
fixed seed (settings ``ALMA_TEST_CORRUPTION_SEED`` and, for a longer run,
``ALMA_TEST_CORRUPTION_COUNT``). For each file, whatever the damage:

* the answer is a staged batch (201) or a refusal with a Polish message (4xx),
  never a server error;
* a staged batch reports every row it counts, each valid row really is valid
  (an ISO date, a non-zero decimal amount, a sender), and each invalid row names
  its reasons;
* when the damage keeps one record per line, no line is lost or invented;
* the donor and payment tables do not change.
"""

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import IMPORT_PAGE_MAX_LIMIT, ROW_ERROR_MESSAGES, RowState
from alma_spei_tests.data import unique_tag
from alma_spei_tests.data.corrupt import (
    GENERATED_SEPARATOR,
    GeneratedFile,
    generated_corruptions,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, imports_steps
from alma_spei_tests.testbase import BaseApiTest

SETTINGS = Settings()

#: One run tag keeps this run's files apart from any earlier upload.
RUN_TAG = unique_tag()

GENERATED = generated_corruptions(SETTINGS.corruption_seed, SETTINGS.corruption_count, RUN_TAG)

#: The answers a damaged file may get: staged, or refused for a stated reason.
ACCEPTABLE = {
    HTTPStatus.CREATED,
    HTTPStatus.BAD_REQUEST,
    HTTPStatus.CONFLICT,
    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
}
#: A normalized amount: a non-zero decimal with at most four places.
AMOUNT = re.compile(r"-?[0-9]{1,16}(\.[0-9]{1,4})?")


@allure.feature("Negative import cases")
class TestGeneratedCorruptions(BaseApiTest):
    @pytest.mark.parametrize(
        "generated",
        [pytest.param(g, id=f"{i:03d}-{g.label}") for i, g in enumerate(GENERATED)],
    )
    def test_a_generated_corrupt_file_keeps_the_invariants(
        self, api: AlmaSpeiApi, db: DbQueries, generated: GeneratedFile
    ):
        # 1. Note the donor and payment tables
        # 2. Upload the generated file
        # 3. Verification: staged or refused with a Polish message, never a server error; a
        #    staged report accounts for its rows and accepts only valid data; the donor and
        #    payment tables are unchanged
        before = db_steps.read_canonical_counts(db)
        response = imports_steps.upload(
            api,
            f"{RUN_TAG}-{generated.label}.csv",
            generated.content,
            separator=GENERATED_SEPARATOR,
        )
        with soft_assertions():
            assert_that(response.status_code).described_as(
                f"a damaged file ({generated.damage}) should be staged or refused, never an error"
                f" (body: {response.text[:300]})"
            ).is_in(*ACCEPTABLE)
            if response.status_code == HTTPStatus.CREATED:
                assert_report_is_sound(api, response.json(), generated)
            else:
                assert_that(response.json().get("message", "")).described_as(
                    "a refusal should explain itself in Polish"
                ).is_not_empty()
            assert_that(db_steps.read_canonical_counts(db)).described_as(
                "uploading should not touch the donor and payment tables"
            ).is_equal_to(before)


# --- file-local helpers -------------------------------------------------------
def assert_report_is_sound(api: AlmaSpeiApi, body: dict[str, Any], generated: GeneratedFile):
    batch = body["batch"]
    rows = all_rows(api, batch["id"], batch["total-rows"])
    valid = [r for r in rows if r["validation-state"] == RowState.VALID]
    invalid = [r for r in rows if r["validation-state"] == RowState.INVALID]
    assert_that((len(rows), len(valid), len(invalid))).described_as(
        "the report should list exactly the rows the batch counts"
    ).is_equal_to((batch["total-rows"], batch["valid-rows"], batch["invalid-rows"]))
    for row in valid:
        assert_that(valid_payload_problems(row["payload"])).described_as(
            f"valid row {row['row-number']} should hold valid data"
        ).is_empty()
    for row in invalid:
        assert_that([e["message"] for e in row["errors"]]).described_as(
            f"invalid row {row['row-number']} should give its Polish reasons"
        ).is_not_empty().is_subset_of(set(ROW_ERROR_MESSAGES.values()))
    if generated.record_lines is not None:
        assert_that(len(rows)).described_as(
            "no line should be lost or invented when every line is one record"
        ).is_equal_to(generated.record_lines)


def all_rows(api: AlmaSpeiApi, batch_id: str, total: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for offset in range(0, max(total, 1), IMPORT_PAGE_MAX_LIMIT):
        page = imports_steps.read_rows(api, batch_id, limit=IMPORT_PAGE_MAX_LIMIT, offset=offset)
        rows += page.json()["rows"]
    return rows


def valid_payload_problems(payload: dict[str, Any]) -> list[str]:
    problems = []
    try:
        dt.date.fromisoformat(payload["date"] or "")
    except ValueError:
        problems.append(f"date {payload['date']!r} is not an ISO date")
    amount = payload["amount"] or ""
    try:
        if not AMOUNT.fullmatch(amount) or Decimal(amount) == 0:
            problems.append(f"amount {amount!r} is not a non-zero decimal")
    except InvalidOperation:
        problems.append(f"amount {amount!r} is not a decimal")
    if not (payload["sender"] or "").strip():
        problems.append("the sender is blank")
    return problems
