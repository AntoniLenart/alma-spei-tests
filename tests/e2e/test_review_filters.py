"""E2E tests for the review filters and the suggestions beside an exception (tasks 61-62).

The browser borrows the administrator's API session. Batches are staged through
the API from senders written as ``name, street, NN-NNN city``. The import summary
shows the transfers in two views - "Do wyjaśnienia" and "Dopasowane w 100%" - and
an exception opens with the suggested donors and their Polish reasons. Choosing
a suggestion only prepares the draft: the payment question still follows.
"""

from typing import Any

import allure
from assertpy import assert_that
from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import DecisionKind, MatchReason
from alma_spei_tests.data import Financial, new_donor_profile, sender_of, sender_with_address
from alma_spei_tests.pages import ReviewMessages
from alma_spei_tests.steps import imports_steps, review_steps, ui_steps
from alma_spei_tests.testbase import BaseE2ETest

#: An address no test donor uses, for a namesake of the donor.
ELSEWHERE = ("ul. Odległa 3", "00-950", "Innowo")


@allure.feature("Review filters UI")
class TestReviewFilters(BaseE2ETest):
    def test_the_filters_split_exact_matches_from_exceptions(
        self, signed_in_page: Page, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage an exact match for the donor (row 1) and a sender without an address (row 2)
        # 2. Open the batch and run the matching
        # 3. Verify the exceptions view is shown, with row 2 only, and both views are counted
        # 4. Switch to "Dopasowane w 100%"
        # 5. Verification: row 1 with the donor's name, read-only (no way to explain it)
        filename = f"{tag}.csv"
        batch_id = imports_steps.stage_senders(api, tag, [sender_of(donor), donor["name"]])
        review = ui_steps.open_review_batch(signed_in_page, batch_id, filename)
        ui_steps.run_matching(review)
        exceptions = review.filter_button(ReviewMessages.exceptions_filter(1))
        exact = review.filter_button(ReviewMessages.exact_filter(1))
        expect(exceptions).to_have_attribute("aria-pressed", "true")
        expect(review.exception_cards).to_have_count(1)
        expect(review.exception_card(donor["name"])).to_be_visible()
        exact.click()
        expect(exact).to_have_attribute("aria-pressed", "true")
        expect(review.exception_cards).to_have_count(1)
        expect(review.exception_cards).to_contain_text(sender_of(donor))
        expect(review.exception_cards.locator("strong").nth(1)).to_have_text(donor["name"])
        expect(review.exception_cards.get_by_role("button")).to_have_count(0)

    def test_without_exact_matches_the_view_says_so(
        self, signed_in_page: Page, staged_upload: dict[str, Any]
    ):
        # 1. Open a staged batch of senders without an address and run the matching
        # 2. Switch to "Dopasowane w 100%"
        # 3. Verification: the view says there are no exact matches
        batch = staged_upload["batch"]
        review = ui_steps.open_review_batch(signed_in_page, batch["id"], batch["original-filename"])
        ui_steps.run_matching(review)
        review.filter_button(ReviewMessages.exact_filter(0)).click()
        expect(review.summary).to_contain_text(ReviewMessages.NO_EXACT_MATCHES)
        expect(review.exception_cards).to_have_count(0)


@allure.feature("Review filters UI")
class TestSuggestionsUi(BaseE2ETest):
    def test_a_suggested_donor_is_explained_and_can_be_chosen(
        self, signed_in_page: Page, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Stage a row from the donor's name at another address, open it and run the matching
        # 2. Explain the row
        # 3. Verify the donor is suggested with its Polish reason
        # 4. Choose it, answer the payment question and save
        # 5. Verification: back on the summary; the row is linked to that donor
        filename = f"{tag}.csv"
        sender = sender_with_address(donor["name"], *ELSEWHERE)
        batch_id = imports_steps.stage_senders(api, tag, [sender])
        review = ui_steps.open_review_batch(signed_in_page, batch_id, filename)
        ui_steps.run_matching(review)
        ui_steps.explain_exception(review, 1, sender)
        expect(review.candidate_card(donor["name"])).to_contain_text(MatchReason.NAME)
        ui_steps.choose_suggested_donor(review, donor["name"])
        ui_steps.settle_payment_via_form(review, Financial())
        ui_steps.wait_for_summary(review, filename)
        decision = review_steps.read_decision(api, batch_id, 1).json()["decision"]
        assert_that((decision["kind"], decision["donor-id"])).described_as(
            "the chosen suggestion should be saved as the row's donor"
        ).is_equal_to((DecisionKind.EXISTING_DONOR, donor["id"]))

    def test_a_sender_like_nobody_is_offered_as_a_new_donor(
        self, signed_in_page: Page, api: AlmaSpeiApi, tag: str
    ):
        # 1. Stage a row from an identity nobody resembles, open it and run the matching
        #    without a type for new donors
        # 2. Explain the row
        # 3. Verification: no suggestions, and the hint to consider a new donor
        filename = f"{tag}.csv"
        profile = new_donor_profile(tag=tag)
        sender = sender_with_address(
            profile.name, profile.street or "", profile.postal_code or "", profile.city
        )
        batch_id = imports_steps.stage_senders(api, tag, [sender])
        review = ui_steps.open_review_batch(signed_in_page, batch_id, filename)
        ui_steps.run_matching(review)
        ui_steps.explain_exception(review, 1, sender)
        expect(review.donor_choice).to_contain_text(ReviewMessages.NEW_PROFILE_HINT)
        expect(review.candidate_cards).to_have_count(0)
