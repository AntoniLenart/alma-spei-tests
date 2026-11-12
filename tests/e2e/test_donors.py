"""E2E tests for the donor list and donor card in the Polish UI.

Donors are created through the API with a per-test tag; the browser borrows the
administrator's API session (``signed_in_page``) and searches by that tag.
"""

from typing import Any

import allure
from assertpy import assert_that
from playwright.sync_api import Page, expect

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import INITIAL_DONOR_VERSION, AuditAction, EntityType
from alma_spei_tests.data import DonorFactory, DonorProfile, new_donor_profile
from alma_spei_tests.pages import DonorMessages
from alma_spei_tests.steps import donors_steps, ui_steps
from alma_spei_tests.testbase import BaseE2ETest

#: Appended to a donor's name by the edit scenario.
RENAMED_SUFFIX = " (zmieniony)"


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


@allure.feature("Donor card UI")
class TestDonorCardUi(BaseE2ETest):
    def test_card_shows_profile_payments_and_creation_history(
        self, signed_in_page: Page, donor: dict[str, Any], donor_profile: DonorProfile, tag: str
    ):
        # 1. Open the donor list and search for the tagged donor
        # 2. Open its card
        # 3. Verification: the city is shown, no payments, and a single creation entry in history
        donors = ui_steps.open_donor_list(signed_in_page)
        ui_steps.search_donors(donors, tag)
        card = ui_steps.open_donor_card(donors, donor_profile.name)
        expect(card.profile_value(DonorMessages.CITY_FIELD)).to_have_text(donor_profile.city)
        expect(card.no_payments).to_be_visible()
        expect(card.history_entries).to_have_text([DonorMessages.ACTION_LABELS[AuditAction.CREATE]])

    def test_editing_the_name_saves_and_is_recorded_in_history(
        self,
        signed_in_page: Page,
        api: AlmaSpeiApi,
        donor: dict[str, Any],
        donor_profile: DonorProfile,
        tag: str,
    ):
        # 1. Open the tagged donor's card
        # 2. Edit the name and save
        # 3. Verification: save confirmation, new heading, newest history entry is an edit,
        #    and the API reports the new name at the next version
        new_name = donor_profile.name + RENAMED_SUFFIX
        donors = ui_steps.open_donor_list(signed_in_page)
        ui_steps.search_donors(donors, tag)
        card = ui_steps.open_donor_card(donors, donor_profile.name)
        ui_steps.edit_and_save(card, "name", new_name)
        ui_steps.wait_until_saved(card)
        expect(card.heading).to_have_text(new_name)
        expect(card.history_entries.first).to_have_text(
            DonorMessages.ACTION_LABELS[AuditAction.UPDATE]
        )
        stored = donors_steps.get_donor(api, donor["id"]).json()["donor"]
        assert_that((stored["name"], stored["version"])).described_as(
            "the saved edit should reach the backend as a new version"
        ).is_equal_to((new_name, INITIAL_DONOR_VERSION + 1))
