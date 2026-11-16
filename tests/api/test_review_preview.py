"""API tests for review readiness blockers and immutable import previews (task 38).

A preview is only built when every staged row has a complete, current decision.
It is an immutable snapshot of the planned effects - new donor profiles once per
proposal, unchanged existing donors, and one new payment per row - with exact
totals per explicit currency. Building it applies nothing.
"""

from decimal import Decimal
from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error, assert_error_includes, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    OTHER_CURRENCY,
    REVIEW_CURRENCY,
    ApiErrorPayload,
    BlockerCode,
    Header,
    ImportState,
    PreviewItemKind,
    ReviewErrorPayload,
    ReviewEventType,
)
from alma_spei_tests.data import (
    BankRow,
    BankStatement,
    Financial,
    existing_donor,
    new_donor_profile,
    proposed_donor,
)
from alma_spei_tests.steps import imports_steps, review_steps
from alma_spei_tests.testbase import BaseApiTest

#: A refund-like line: parser-valid, but negative amounts have no approved policy yet.
NEGATIVE_AMOUNT = "-12,50"
#: An impossible date: the row is staged as invalid.
INVALID_DATE = "2026-02-30"


@allure.feature("Import preview")
class TestReadinessBlockers(BaseApiTest):
    def test_every_undecided_row_is_a_blocker(self, api: AlmaSpeiApi, staged_batch_id: str):
        # 1. Read the blockers of a freshly staged batch
        # 2. Verification: both rows lack a decision
        body = review_steps.read_blockers(api, staged_batch_id).json()
        assert_that(blocker_codes(body)).described_as(
            "every undecided row should block the preview"
        ).is_equal_to([(1, BlockerCode.MISSING_DECISION), (2, BlockerCode.MISSING_DECISION)])

    def test_an_invalid_row_stays_a_blocker(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Stage a statement with one valid line and one with an impossible date
        # 2. Read its blockers
        # 3. Verification: the invalid row blocks as invalid-row (it never disappears)
        invalid = BankRow(INVALID_DATE, bank_statement.rows[0].sender, tag, "1,00")
        statement = BankStatement([bank_statement.rows[0], invalid])
        batch = imports_steps.upload_staged(api, f"{tag}.csv", statement.to_csv())["batch"]
        body = review_steps.read_blockers(api, batch["id"]).json()
        assert_that(blocker_codes(body)).contains((2, BlockerCode.INVALID_ROW))

    def test_a_negative_amount_blocks_even_when_decided(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage a statement whose only line has a negative amount
        # 2. Link it to a donor as a complete decision
        # 3. Verification: the row blocks as unsupported-amount
        statement = BankStatement([BankRow("2026-02-01", donor["name"], tag, NEGATIVE_AMOUNT)])
        batch = imports_steps.upload_staged(api, f"{tag}.csv", statement.to_csv())["batch"]
        review_steps.decide(api, batch["id"], 1, existing_donor(donor))
        body = review_steps.read_blockers(api, batch["id"]).json()
        assert_that(blocker_codes(body)).described_as(
            "a negative payment should wait for a refund policy"
        ).is_equal_to([(1, BlockerCode.UNSUPPORTED_AMOUNT)])

    def test_a_decided_batch_has_no_blockers(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Decide both rows of a staged batch (fixture)
        # 2. Verification: no blockers remain
        body = review_steps.read_blockers(api, decided_upload["batch"]["id"]).json()
        assert_that((body["blockers"], body["total"])).described_as(
            "a fully decided batch should be ready"
        ).is_equal_to(([], 0))


@allure.feature("Import preview")
class TestPreview(BaseApiTest):
    def test_preview_is_refused_while_rows_are_undecided(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Decide only row 1 of a staged batch
        # 2. Request a preview
        # 3. Verification: 409 review-blocked listing row 2, and no preview was recorded
        review_steps.decide(api, staged_batch_id, 1, existing_donor(donor))
        response = review_steps.prepare_preview(api, staged_batch_id)
        body = response.json()
        with soft_assertions():
            assert_error_includes(response, HTTPStatus.CONFLICT, ReviewErrorPayload.REVIEW_BLOCKED)
            assert_that(
                (
                    [(b["row-number"], b["code"]) for b in body.get("blockers", [])],
                    body.get("total"),
                )
            ).described_as("the refusal should name the undecided row").is_equal_to(
                ([(2, BlockerCode.MISSING_DECISION)], 1)
            )

    @pytest.mark.smoke
    def test_ready_preview_plans_one_new_payment_per_row(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Decide both rows for one existing donor (fixture)
        # 2. Request a preview
        # 3. Verification: 201; two new payments, no new donors, the PLN total of both rows
        batch_id = decided_upload["batch"]["id"]
        response = review_steps.prepare_preview(api, batch_id)
        summary = response.json()["preview"]["summary"]
        with soft_assertions():
            assert_status(response, HTTPStatus.CREATED, "preparing a ready preview")
            assert_that(
                (summary["new-donors"], summary["new-payments"], summary["duplicate-references"])
            ).described_as("the preview should plan two payments for one donor").is_equal_to(
                (0, 2, 0)
            )
            assert_that(totals(summary)).described_as(
                "the PLN total should be the exact sum of both rows"
            ).is_equal_to({REVIEW_CURRENCY: staged_total(api, batch_id)})

    def test_preview_items_list_the_donor_once_and_each_payment(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Prepare a preview of a batch decided for one existing donor
        # 2. Read its items
        # 3. Verification: the unchanged donor first, then a new payment for rows 1 and 2
        batch_id = decided_upload["batch"]["id"]
        preview = review_steps.create_preview(api, batch_id)["preview"]
        items = review_steps.read_preview_items(api, batch_id, preview["id"]).json()["items"]
        with soft_assertions():
            assert_that([(i["kind"], i["target-id"], i["row-number"]) for i in items]).described_as(
                "the plan should reference the donor once and add a payment per row"
            ).is_equal_to(
                [
                    (PreviewItemKind.EXISTING_DONOR_REFERENCE, donor["id"], None),
                    (PreviewItemKind.NEW_PAYMENT, None, 1),
                    (PreviewItemKind.NEW_PAYMENT, None, 2),
                ]
            )
            assert_that(items[0]["payload"]["changes"]).described_as(
                "an existing donor should get no field changes"
            ).is_empty()

    def test_a_shared_proposal_becomes_one_new_donor(
        self, api: AlmaSpeiApi, staged_batch_id: str, tag: str
    ):
        # 1. Propose one donor and link both rows to it
        # 2. Prepare a preview
        # 3. Verification: one new donor and two new payments
        proposal = review_steps.create_proposal(
            api, staged_batch_id, new_donor_profile(tag=tag).to_payload()
        )
        review_steps.decide_rows(
            api, staged_batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        summary = review_steps.create_preview(api, staged_batch_id)["preview"]["summary"]
        assert_that((summary["new-donors"], summary["new-payments"])).described_as(
            "a reused proposal should create a single donor"
        ).is_equal_to((1, 2))

    def test_totals_are_kept_per_currency(
        self, api: AlmaSpeiApi, staged_batch_id: str, donor: dict[str, Any]
    ):
        # 1. Decide row 1 as a PLN payment and row 2 as a EUR payment
        # 2. Prepare a preview
        # 3. Verification: one total per currency - amounts in different currencies never add up
        review_steps.decide_rows(
            api,
            staged_batch_id,
            [
                existing_donor(donor, Financial(currency=REVIEW_CURRENCY)),
                existing_donor(donor, Financial(currency=OTHER_CURRENCY)),
            ],
        )
        summary = review_steps.create_preview(api, staged_batch_id)["preview"]["summary"]
        amounts = staged_amounts(api, staged_batch_id)
        assert_that(totals(summary)).described_as(
            "each currency should keep its own exact total"
        ).is_equal_to({REVIEW_CURRENCY: amounts[0], OTHER_CURRENCY: amounts[1]})

    def test_preview_leaves_the_batch_under_review(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Prepare a preview of a decided batch
        # 2. Verification: the batch keeps its state and version - a preview is not an approval
        batch = decided_upload["batch"]
        body = review_steps.create_preview(api, batch["id"])
        assert_that((body["batch"]["state"], body["batch"]["version"])).described_as(
            "a preview should not move the batch on"
        ).is_equal_to((ImportState.REVIEW, batch["version"]))

    def test_a_changed_decision_makes_the_preview_stale(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Prepare a preview of a decided batch and read it back (current)
        # 2. Change row 2's evidence note
        # 3. Verification: the same preview now reads as stale
        batch_id = decided_upload["batch"]["id"]
        preview_id = review_steps.create_preview(api, batch_id)["preview"]["id"]
        fresh = review_steps.read_preview(api, batch_id, preview_id).json()["stale"]
        changed = Financial().with_changes(evidence="Poprawione uzasadnienie testowe.")
        review_steps.decide(api, batch_id, 2, existing_donor(donor, changed))
        stale = review_steps.read_preview(api, batch_id, preview_id).json()["stale"]
        assert_that((fresh, stale)).described_as(
            "a preview should become stale once a decision changes"
        ).is_equal_to((False, True))

    def test_preview_items_are_paged(self, api: AlmaSpeiApi, decided_upload: dict[str, Any]):
        # 1. Prepare a preview of three items
        # 2. Read its items two at a time, from offset 2
        # 3. Verification: the last item only, with the full total
        batch_id = decided_upload["batch"]["id"]
        preview_id = review_steps.create_preview(api, batch_id)["preview"]["id"]
        body = review_steps.read_preview_items(api, batch_id, preview_id, limit=2, offset=2).json()
        assert_that(([i["ordinal"] for i in body["items"]], body["total"])).described_as(
            "the second page should hold the third item of three"
        ).is_equal_to(([3], 3))

    def test_preview_creation_is_journaled(self, api: AlmaSpeiApi, staged_batch_id: str, tag: str):
        # 1. Propose a donor, link both rows to it and prepare a preview
        # 2. Read the review history
        # 3. Verification: one proposal, two decisions and the preview, in order
        proposal = review_steps.create_proposal(
            api, staged_batch_id, new_donor_profile(tag=tag).to_payload()
        )
        review_steps.decide_rows(
            api, staged_batch_id, [proposed_donor(proposal), proposed_donor(proposal)]
        )
        review_steps.create_preview(api, staged_batch_id)
        events = review_steps.read_review_events(api, staged_batch_id).json()["events"]
        assert_that([e["event-type"] for e in events]).described_as(
            "the review history should record every write in order"
        ).is_equal_to(
            [
                ReviewEventType.PROPOSAL_CREATED,
                ReviewEventType.DECISION_SAVED,
                ReviewEventType.DECISION_SAVED,
                ReviewEventType.PREVIEW_CREATED,
            ]
        )

    def test_unknown_preview_is_not_found(self, api: AlmaSpeiApi, staged_batch_id: str):
        # 1. Read a preview id that does not exist for the batch
        # 2. Verification: 404 preview not-found
        response = review_steps.read_preview(api, staged_batch_id, str(_UNKNOWN_ID))
        assert_error(response, HTTPStatus.NOT_FOUND, ReviewErrorPayload.PREVIEW_NOT_FOUND)

    def test_preview_without_csrf_is_refused(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Request a preview without the X-CSRF-Token header
        # 2. Verification: 403 csrf
        batch = decided_upload["batch"]
        response = review_steps.request_preview(
            api, batch["id"], batch["version"], headers={Header.CSRF_TOKEN: None}
        )
        assert_error(response, HTTPStatus.FORBIDDEN, ReviewErrorPayload.CSRF)

    def test_anonymous_client_cannot_read_blockers(
        self, anonymous_api: AlmaSpeiApi, staged_batch_id: str
    ):
        # 1. Read the blockers without signing in
        # 2. Verification: 401 unauthenticated
        response = review_steps.read_blockers(anonymous_api, staged_batch_id)
        assert_error(response, HTTPStatus.UNAUTHORIZED, ApiErrorPayload.UNAUTHENTICATED)


# --- file-local helpers -------------------------------------------------------
_UNKNOWN_ID = "00000000-0000-4000-8000-000000000000"


def blocker_codes(body: dict[str, Any]) -> list[tuple[int, str]]:
    return [(b["row-number"], b["code"]) for b in body["blockers"]]


def totals(summary: dict[str, Any]) -> dict[str, Decimal]:
    return {t["currency"]: Decimal(t["amount"]) for t in summary["totals"]}


def staged_amounts(api: AlmaSpeiApi, batch_id: str) -> list[Decimal]:
    """The parsed amounts of the batch's rows, in row order."""
    rows = imports_steps.read_rows(api, batch_id).json()["rows"]
    return [Decimal(row["payload"]["amount"]) for row in rows]


def staged_total(api: AlmaSpeiApi, batch_id: str) -> Decimal:
    return sum(staged_amounts(api, batch_id), Decimal(0))
