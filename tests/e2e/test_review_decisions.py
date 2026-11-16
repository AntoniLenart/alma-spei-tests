"""E2E tests for review decisions, donor proposals and the import preview (task 38).

The browser borrows the administrator's API session. Batches are staged (and,
where the form is not under test, decided) through the API. Nothing is chosen
for the reviewer: the donor, the currency and the payment treatment are typed
or picked explicitly in each test.
"""

from typing import Any

import allure
from assertpy import assert_that, soft_assertions
from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import REVIEW_CURRENCY, BlockerCode, DecisionKind
from alma_spei_tests.data import DonorFactory, Financial, new_donor_profile
from alma_spei_tests.db import DbQueries
from alma_spei_tests.pages import ReviewMessages
from alma_spei_tests.steps import db_steps, review_steps, ui_steps
from alma_spei_tests.testbase import BaseE2ETest

#: Valid rows in the default two-line statement.
STAGED_VALID_ROWS = 2


@allure.feature("Review decisions UI")
class TestDecisionEditorUi(BaseE2ETest):
    def test_linking_the_compared_donor_saves_a_complete_decision(
        self,
        signed_in_page: Page,
        api: AlmaSpeiApi,
        staged_upload: dict[str, Any],
        donor: dict[str, Any],
        tag: str,
        settings: Settings,
    ):
        # 1. Open a staged batch and compare row 1 with the tagged donor
        # 2. Choose that donor as the target, type the currency and evidence, mark it a new
        #    payment with the overlap check, and save
        # 3. Verification: the saved line names the reviewer and a complete decision; the
        #    progress counts one row; the API stores the link to that donor
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.compare_with_donor(review, tag, donor["name"], donor["city"])
        ui_steps.choose_compared_donor(review, donor["name"])
        ui_steps.fill_payment_review(review, Financial())
        ui_steps.save_decision_via_form(review)
        expect(review.saved_notice).to_contain_text(settings.admin_display_name)
        expect(review.saved_notice).to_contain_text(ReviewMessages.COMPLETE)
        expect(review.progress_text()).to_have_text(
            ReviewMessages.progress(1, STAGED_VALID_ROWS, 0)
        )
        saved = review_steps.read_decision(api, batch["id"], 1).json()["decision"]
        assert_that((saved["kind"], saved["donor-id"])).described_as(
            "the form should save the explicit link to the compared donor"
        ).is_equal_to((DecisionKind.EXISTING_DONOR, donor["id"]))

    def test_a_saved_decision_is_shown_again_after_reloading(
        self, signed_in_page: Page, decided_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Decide both rows through the API (fixture)
        # 2. Open the batch in the browser
        # 3. Verification: row 1 shows its saved, complete decision with the donor and currency
        batch = decided_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        expect(review.saved_notice).to_contain_text(ReviewMessages.COMPLETE)
        expect(review.target_line).to_have_text(
            ReviewMessages.target(ReviewMessages.TARGET_EXISTING, donor["name"])
        )
        expect(review.currency_input).to_have_value(REVIEW_CURRENCY)

    def test_a_new_profile_proposal_can_receive_the_row(
        self, signed_in_page: Page, api: AlmaSpeiApi, staged_upload: dict[str, Any], tag: str
    ):
        # 1. Open a staged batch
        # 2. Prepare a new profile by hand (type, name, city, both checks), save and use it
        # 3. Review the payment and save the decision
        # 4. Verification: the row is linked to the new proposal, which is not a donor yet
        batch = staged_upload["batch"]
        profile = new_donor_profile(tag=tag)
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.propose_and_use_donor(review, profile)
        ui_steps.fill_payment_review(review, Financial())
        ui_steps.save_decision_via_form(review)
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
        donor_factory: DonorFactory,
        tag: str,
    ):
        # 1. Create a tagged donor and archive it
        # 2. Open a staged batch, search archived donors and compare with it
        # 3. Verification: the choose button is disabled and the archive notice is shown
        archived = donor_factory(new_donor_profile(tag=tag))
        db_steps.archive_donor(db, archived["id"])
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        review.status_filter_select.select_option("archived")
        ui_steps.compare_with_donor(review, tag, archived["name"], archived["city"])
        expect(review.editor_button(ReviewMessages.CHOOSE_COMPARED)).to_be_disabled()
        expect(review.editor).to_contain_text(ReviewMessages.ARCHIVED_NOT_SELECTABLE)


@allure.feature("Review decisions UI")
class TestPreviewUi(BaseE2ETest):
    def test_preview_is_blocked_until_every_row_is_decided(
        self, signed_in_page: Page, staged_upload: dict[str, Any]
    ):
        # 1. Open an undecided staged batch
        # 2. Prepare the preview
        # 3. Verification: the blocked alert and a missing-decision line for both rows
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.prepare_preview_via_form(review)
        missing = ReviewMessages.BLOCKER_MESSAGES[BlockerCode.MISSING_DECISION]
        expect(review.preview_alert).to_have_text(ReviewMessages.PREVIEW_BLOCKED)
        expect(review.blocker_items).to_have_text(
            [ReviewMessages.blocker(1, missing), ReviewMessages.blocker(2, missing)]
        )

    def test_a_ready_preview_shows_the_planned_payments(
        self, signed_in_page: Page, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Decide both rows for one donor through the API (fixture)
        # 2. Open the batch and prepare the preview
        # 3. Verification: no new profiles and two new payments with their PLN total; the
        #    unchanged donor and both payments are listed
        batch = decided_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.prepare_preview_via_form(review)
        expect(review.preview_text(ReviewMessages.preview_summary(0, 2, 0))).to_be_visible()
        total = staged_total_text(api, batch["id"])
        expect(
            review.preview_text(ReviewMessages.preview_total(total, REVIEW_CURRENCY))
        ).to_be_visible()
        expect(review.preview_items).to_have_count(3)


# --- file-local helpers -------------------------------------------------------
def staged_total_text(api: AlmaSpeiApi, batch_id: str) -> str:
    """The preview's PLN total as the API reports it (the source of truth for the screen)."""
    preview = review_steps.create_preview(api, batch_id)["preview"]
    return preview["summary"]["totals"][0]["amount"]
