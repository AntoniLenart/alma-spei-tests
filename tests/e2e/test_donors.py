"""E2E tests for the donor list in the Polish UI.

Donors are created through the API with a per-test tag; the browser borrows the
administrator's API session (``signed_in_page``) and searches by that tag.
"""

from typing import Any

import allure
from assertpy import assert_that
from playwright.sync_api import Page, expect

from alma_spei_tests.constants import EntityType
from alma_spei_tests.data import DonorFactory, DonorProfile, new_donor_profile
from alma_spei_tests.pages import DonorMessages
from alma_spei_tests.steps import ui_steps
from alma_spei_tests.testbase import BaseE2ETest


@allure.feature("Donor list UI")
class TestDonorListUi(BaseE2ETest):
    def test_search_shows_the_matching_donor_row(
        self, signed_in_page: Page, donor: dict[str, Any], donor_profile: DonorProfile, tag: str
    ):
        # 1. Open the donor list with the administrator's session
        # 2. Search for this test's tag
        # 3. Verification: one row with the name, Polish type label, city and "Aktywny"
        donors = ui_steps.open_donor_list(signed_in_page)
        ui_steps.search_donors(donors, tag)
        ui_steps.wait_for_row_count(donors, 1)
        expect(donors.results_summary).to_have_text(DonorMessages.results_summary(1, 1, 1))
        assert_that(donors.row_cells(donor_profile.name)).described_as(
            "the row should show the donor's name, type, city and status"
        ).is_equal_to(
            [
                donor_profile.name,
                DonorMessages.ENTITY_LABELS[donor_profile.entity_type],
                donor_profile.city,
                DonorMessages.ACTIVE,
            ]
        )

    def test_search_without_matches_shows_the_empty_message(self, signed_in_page: Page, tag: str):
        # 1. Open the donor list
        # 2. Search for a tag no donor carries
        # 3. Verification: the Polish "no donors" message is shown
        donors = ui_steps.open_donor_list(signed_in_page)
        ui_steps.search_donors(donors, tag)
        expect(donors.empty_message).to_be_visible()

    def test_type_filter_narrows_the_list(
        self, signed_in_page: Page, donor_factory: DonorFactory, tag: str
    ):
        # 1. Create a tagged individual and a tagged business
        # 2. Search for the tag, then filter to businesses
        # 3. Verification: only the business row remains
        donor_factory(new_donor_profile(EntityType.INDIVIDUAL, tag=tag))
        business = donor_factory(new_donor_profile(EntityType.BUSINESS, tag=tag))
        donors = ui_steps.open_donor_list(signed_in_page)
        ui_steps.search_donors(donors, tag)
        ui_steps.wait_for_row_count(donors, 2)
        donors.filter_by_type(EntityType.BUSINESS)
        ui_steps.wait_for_row_count(donors, 1)
        expect(donors.open_card_button(business["name"])).to_be_visible()
