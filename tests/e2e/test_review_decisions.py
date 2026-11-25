"""E2E tests for explaining import exceptions and the import summary (tasks 38, 62).

The browser borrows the administrator's API session. Batches are staged (and,
where the screen is not under test, decided) through the API. After the matching,
the default synthetic lines are exceptions; the reviewer explains one by picking
a donor from the catalogue or preparing a new one. That prepares a draft: the
reviewer then types the currency and the evidence, chooses how the payment is
treated and confirms the overlap check before the explanation can be saved.
"""

from typing import Any

import allure
from assertpy import assert_that, soft_assertions
from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    REVIEW_CURRENCY,
    DecisionKind,
    DonorStatusFilter,
)
from alma_spei_tests.data import (
    BankStatement,
    DonorFactory,
    Financial,
    new_donor_profile,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.pages import ReviewMessages
from alma_spei_tests.steps import db_steps, review_steps, ui_steps
from alma_spei_tests.testbase import BaseE2ETest

#: Valid rows in the default two-line statement.
STAGED_VALID_ROWS = 2


@allure.feature("Review decisions UI")
class TestExceptionDecisionsUi(BaseE2ETest):
    def test_assigning_a_catalogue_donor_resolves_the_exception(
        self,
        signed_in_page: Page,
        api: AlmaSpeiApi,
        staged_upload: dict[str, Any],
        bank_statement: BankStatement,
        donor: dict[str, Any],
        tag: str,
    ):
        # 1. Open a staged batch, run the matching and explain row 1
        # 2. Compare row 1 with the tagged donor from the catalogue and assign it
        # 3. Type PLN and the evidence, mark it a new payment with the overlap check, and save
        # 4. Verification: back on the summary with one matched transfer, one new payment and
        #    one exception left; the API stores a complete link to that donor in PLN
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.run_matching(review)
        ui_steps.explain_exception(review, 1, bank_statement.rows[0].sender)
        ui_steps.look_up_donors(review)
        ui_steps.compare_with_donor(review, tag, donor["name"], donor["city"])
        ui_steps.assign_compared_donor(review)
        ui_steps.settle_payment_via_form(review, Financial())
        ui_steps.wait_for_summary(review, batch["original-filename"])
        expect(review.count_value(ReviewMessages.EXCEPTIONS)).to_have_text(
            str(STAGED_VALID_ROWS - 1)
        )
        saved = review_steps.read_decision(api, batch["id"], 1).json()["decision"]
        with soft_assertions():
            assert_that(review.count_values()).described_as(
                "the summary should count the explained transfer as matched"
            ).is_equal_to(ReviewMessages.counts(matched=1, new_payments=1, exceptions=1))
            assert_that(
                (saved["kind"], saved["donor-id"], saved["complete"], saved_currency(saved))
            ).described_as(
                "the explicit choice should be saved as a complete link in the file's currency"
            ).is_equal_to((DecisionKind.EXISTING_DONOR, donor["id"], True, REVIEW_CURRENCY))

    def test_a_new_donor_can_be_prepared_for_an_exception(
        self,
        signed_in_page: Page,
        api: AlmaSpeiApi,
        staged_upload: dict[str, Any],
        bank_statement: BankStatement,
        tag: str,
    ):
        # 1. Open a staged batch, run the matching and explain row 1
        # 2. Prepare a new donor by hand (type, name, city, both checks) and save it
        # 3. Answer the payment question and save the explanation
        # 4. Verification: back on the summary with one new donor; the row is linked to the
        #    new proposal, which is not a donor yet
        batch = staged_upload["batch"]
        profile = new_donor_profile(tag=tag)
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.run_matching(review)
        ui_steps.explain_exception(review, 1, bank_statement.rows[0].sender)
        ui_steps.propose_new_donor(review, profile)
        ui_steps.settle_payment_via_form(review, Financial())
        ui_steps.wait_for_summary(review, batch["original-filename"])
        expect(review.count_value(ReviewMessages.NEW_DONORS)).to_have_text("1")
        saved = review_steps.read_decision(api, batch["id"], 1).json()["decision"]
        proposals = review_steps.list_proposals(api, batch["id"]).json()["proposals"]
        with soft_assertions():
            assert_that((saved["kind"], saved["proposal-id"])).described_as(
                "the row should be linked to the proposal typed in the form"
            ).is_equal_to((DecisionKind.NEW_PROPOSAL, proposals[0]["id"]))
            assert_that(proposals[0]["profile"]["name"]).described_as(
                "the proposal should carry the typed name"
            ).is_equal_to(profile.name)

    def test_an_archived_donor_can_be_compared_but_not_chosen(
        self,
        signed_in_page: Page,
        db: DbQueries,
        staged_upload: dict[str, Any],
        bank_statement: BankStatement,
        donor_factory: DonorFactory,
        tag: str,
    ):
        # 1. Create a tagged donor and archive it
        # 2. Open a staged batch, run the matching and explain row 1
        # 3. Look up archived donors and compare with it
        # 4. Verification: the assign button is disabled and the archive notice is shown
        archived = donor_factory(new_donor_profile(tag=tag))
        db_steps.archive_donor(db, archived["id"])
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.run_matching(review)
        ui_steps.explain_exception(review, 1, bank_statement.rows[0].sender)
        ui_steps.look_up_donors(review, DonorStatusFilter.ARCHIVED)
        ui_steps.compare_with_donor(review, tag, archived["name"], archived["city"])
        expect(review.choice_button(ReviewMessages.ASSIGN)).to_be_disabled()
        expect(review.donor_choice).to_contain_text(ReviewMessages.ARCHIVED_NOTICE)

    def test_an_explanation_needs_the_currency_and_the_overlap_check(
        self,
        signed_in_page: Page,
        api: AlmaSpeiApi,
        staged_upload: dict[str, Any],
        bank_statement: BankStatement,
        donor: dict[str, Any],
        tag: str,
    ):
        # 1. Open a staged batch, run the matching, explain row 1 and assign the tagged donor
        # 2. Verify nothing is filled in for the payment and the save is disabled, with the
        #    currency, evidence, treatment and overlap check listed as missing
        # 3. Answer everything but the overlap check
        # 4. Verify the save is still disabled, with only the overlap check missing
        # 5. Confirm the overlap check and save
        # 6. Verification: back on the summary; the decision is complete in the typed currency
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.run_matching(review)
        ui_steps.explain_exception(review, 1, bank_statement.rows[0].sender)
        ui_steps.look_up_donors(review)
        ui_steps.compare_with_donor(review, tag, donor["name"], donor["city"])
        ui_steps.assign_compared_donor(review)
        save = review.editor_button(ReviewMessages.SAVE_EXPLANATION)
        expect(review.currency_input).to_have_value("")
        expect(save).to_be_disabled()
        expect(review.missing_checks).to_have_text(
            [
                ReviewMessages.MISSING_CURRENCY,
                ReviewMessages.MISSING_EVIDENCE,
                ReviewMessages.MISSING_DISPOSITION,
                ReviewMessages.MISSING_OVERLAP,
            ]
        )
        ui_steps.answer_payment_question(review, Financial(overlap_checked=False))
        expect(save).to_be_disabled()
        expect(review.missing_checks).to_have_text([ReviewMessages.MISSING_OVERLAP])
        ui_steps.tick(review.overlap_checkbox)
        save.click()
        ui_steps.wait_for_summary(review, batch["original-filename"])
        saved = review_steps.read_decision(api, batch["id"], 1).json()["decision"]
        assert_that((saved["complete"], saved_currency(saved))).described_as(
            "the explanation should be saved complete in the typed currency"
        ).is_equal_to((True, REVIEW_CURRENCY))


@allure.feature("Review decisions UI")
class TestSummaryUi(BaseE2ETest):
    def test_exceptions_hold_back_the_approval(
        self, signed_in_page: Page, staged_upload: dict[str, Any]
    ):
        # 1. Open an undecided staged batch and run the matching
        # 2. Verification: the exceptions view lists both rows, and no approval is offered
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.run_matching(review)
        expect(
            review.filter_button(ReviewMessages.exceptions_filter(STAGED_VALID_ROWS))
        ).to_have_attribute("aria-pressed", "true")
        expect(review.exception_cards).to_have_count(STAGED_VALID_ROWS)
        expect(review.summary_button(ReviewMessages.REVIEW_CHANGES)).to_have_count(0)

    def test_a_decided_batch_is_ready_with_its_total(
        self,
        signed_in_page: Page,
        decided_upload: dict[str, Any],
        bank_statement: BankStatement,
    ):
        # 1. Decide both rows for one donor through the API (fixture)
        # 2. Open the batch
        # 3. Verification: two matched transfers and two new payments with their PLN total,
        #    no exceptions, and the approval step is offered
        batch = decided_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        expect(review.ready_card).to_contain_text(ReviewMessages.READY_HEADING)
        with soft_assertions():
            assert_that(review.count_values()).described_as(
                "both decided transfers should count as matched new payments"
            ).is_equal_to(ReviewMessages.counts(matched=2, new_payments=2))
            assert_that(review.total_line.inner_text().strip()).described_as(
                "the summary should add up the new payments in PLN"
            ).is_equal_to(ReviewMessages.total(str(bank_statement.total()), REVIEW_CURRENCY))


# --- file-local helpers -------------------------------------------------------
def saved_currency(decision: dict[str, Any]) -> str | None:
    return (decision.get("financial") or {}).get("currency")
