"""Contract tests: donor responses vs contracts/donors.cljc."""

from typing import Any

import allure

from alma_spei_tests.assertions import assert_matches_contract
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.contracts import (
    DETAIL_RESPONSE,
    DONOR,
    DONORS_RESPONSE,
    HISTORY_RESPONSE,
)
from alma_spei_tests.data import DonorFactory, DonorProfile
from alma_spei_tests.steps import donors_steps
from alma_spei_tests.testbase import BaseContractTest


@allure.feature("Donor contract")
class TestDonorContract(BaseContractTest):
    def test_created_donor_matches_contract(
        self, donor_factory: DonorFactory, donor_profile: DonorProfile
    ):
        # 1. Create a donor
        # 2. Verification: the returned donor satisfies the donor schema of donor-response
        donor = donor_factory(donor_profile)
        assert_matches_contract(donor, DONOR, "donor")

    def test_list_response_matches_contract(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. List donors matching a tagged donor
        # 2. Verification: the body satisfies donors-response
        body = donors_steps.list_donors(api, search=tag).json()
        assert_matches_contract(body, DONORS_RESPONSE, "donors-response")

    def test_card_response_matches_contract(self, api: AlmaSpeiApi, donor: dict[str, Any]):
        # 1. Open a donor card
        # 2. Verification: the body satisfies detail-response
        body = donors_steps.get_donor(api, donor["id"]).json()
        assert_matches_contract(body, DETAIL_RESPONSE, "detail-response")

    def test_history_response_matches_contract(self, api: AlmaSpeiApi, donor: dict[str, Any]):
        # 1. Read a donor's change history
        # 2. Verification: the body satisfies history-response
        body = donors_steps.get_history(api, donor["id"]).json()
        assert_matches_contract(body, HISTORY_RESPONSE, "history-response")
