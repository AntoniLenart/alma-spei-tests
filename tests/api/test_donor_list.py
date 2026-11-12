"""API tests for the donor list: literal search, filters, sorting and pagination.

Every scenario tags its donors and searches by that tag, so donors left behind
by other tests (archived on teardown) never leak into the expectations.
"""

from http import HTTPStatus
from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_ids, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    DONOR_PAGE_MAX_LIMIT,
    DonorSortField,
    DonorStatusFilter,
    EntityType,
    ErrorCode,
    SortDirection,
)
from alma_spei_tests.data import DonorFactory, new_donor_profile, unique_tag
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, donors_steps
from alma_spei_tests.testbase import BaseApiTest

#: Name prefixes / cities in ascending order, for deterministic sort checks.
ORDERED_WORDS = ("Alfa", "Beta", "Gamma")

#: Text that would match everything if search were not literal.
SQL_LIKE_WILDCARD = "%"
SQL_INJECTION_PROBE = "' OR true --"


@allure.feature("Donor list")
class TestDonorSearch(BaseApiTest):
    @pytest.mark.smoke
    def test_search_finds_only_matching_donors(
        self, api: AlmaSpeiApi, donor_factory: DonorFactory, tag: str, other_tag: str
    ):
        # 1. Create two donors with this test's tag and one with a different tag
        # 2. Search by the tag
        # 3. Verification: exactly the two tagged donors are listed and counted
        tagged = [donor_factory(new_donor_profile(tag=tag)) for _ in range(2)]
        donor_factory(new_donor_profile(tag=other_tag))
        body = donors_steps.list_donors(api, search=tag).json()
        with soft_assertions():
            assert_that({d["id"] for d in body["donors"]}).described_as(
                "search should return exactly the tagged donors"
            ).is_equal_to({d["id"] for d in tagged})
            assert_that(body["total"]).described_as("total should count the matches").is_equal_to(
                len(tagged)
            )

    def test_search_ignores_letter_case(self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str):
        # 1. Create a tagged donor
        # 2. Search by the tag in upper case
        # 3. Verification: the donor is found
        donors = donors_steps.list_tagged(api, tag.upper())
        assert_ids(donors, [donor["id"]], "a case-insensitive search")

    @pytest.mark.parametrize(
        "suffix",
        [
            pytest.param(SQL_LIKE_WILDCARD, id="like-wildcard"),
            pytest.param(SQL_INJECTION_PROBE, id="sql-probe"),
        ],
    )
    def test_search_text_is_matched_literally(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str, suffix: str
    ):
        # 1. Create a tagged donor
        # 2. Search for the tag followed by SQL metacharacters
        # 3. Verification: nothing matches (the text is not interpreted as a pattern or SQL)
        body = donors_steps.list_donors(api, search=f"{tag}{suffix}").json()
        assert_that(body["total"]).described_as(
            "search text should be matched literally"
        ).is_equal_to(0)


@allure.feature("Donor list")
class TestDonorFilters(BaseApiTest):
    def test_entity_type_filter(self, api: AlmaSpeiApi, donor_factory: DonorFactory, tag: str):
        # 1. Create one tagged donor of each entity type
        # 2. List tagged donors filtered to businesses
        # 3. Verification: only the business is listed
        created = {t: donor_factory(new_donor_profile(t, tag=tag)) for t in EntityType}
        donors = donors_steps.list_tagged(api, tag, entity_type=EntityType.BUSINESS)
        assert_ids(donors, [created[EntityType.BUSINESS]["id"]], "the business filter")

    def test_status_filter_separates_active_and_archived(
        self, api: AlmaSpeiApi, db: DbQueries, donor_factory: DonorFactory, tag: str
    ):
        # 1. Create two tagged donors and archive one of them
        # 2. List tagged donors with the default, archived and all statuses
        # 3. Verification: default shows the active one, archived the other, all both
        active = donor_factory(new_donor_profile(tag=tag))
        archived = donor_factory(new_donor_profile(tag=tag))
        db_steps.archive_donor(db, archived["id"])
        default = donors_steps.list_tagged(api, tag)
        only_archived = donors_steps.list_tagged(api, tag, status=DonorStatusFilter.ARCHIVED)
        everyone = donors_steps.list_tagged(api, tag, status=DonorStatusFilter.ALL)
        with soft_assertions():
            assert_ids(default, [active["id"]], "the default (active) list")
            assert_ids(only_archived, [archived["id"]], "the archived list")
            assert_that({d["id"] for d in everyone}).described_as(
                "the all-status list should include both donors"
            ).is_equal_to({active["id"], archived["id"]})


@allure.feature("Donor list")
class TestDonorSortingAndPaging(BaseApiTest):
    @pytest.mark.parametrize("field", [DonorSortField.NAME, DonorSortField.CITY])
    def test_sorting_in_both_directions(
        self, api: AlmaSpeiApi, ordered_donors: list[dict[str, Any]], tag: str, field: str
    ):
        # 1. Create three tagged donors whose names and cities sort Alfa < Beta < Gamma
        # 2. List them sorted by the field ascending, then descending
        # 3. Verification: ascending is Alfa..Gamma and descending is the reverse
        expected = [d["id"] for d in ordered_donors]
        ascending = donors_steps.list_tagged(
            api, tag, sort_by=field, sort_direction=SortDirection.ASC
        )
        descending = donors_steps.list_tagged(
            api, tag, sort_by=field, sort_direction=SortDirection.DESC
        )
        with soft_assertions():
            assert_ids(ascending, expected, f"ascending sort by {field}")
            assert_ids(descending, expected[::-1], f"descending sort by {field}")

    def test_pagination_pages_through_the_results(
        self, api: AlmaSpeiApi, ordered_donors: list[dict[str, Any]], tag: str
    ):
        # 1. Create three tagged donors in a known order
        # 2. Read pages of two: offset 0, offset 2, and past the end
        # 3. Verification: pages hold 2, 1 and 0 donors in order, each reporting a total of 3
        ids = [d["id"] for d in ordered_donors]
        pages = [
            donors_steps.list_donors(api, search=tag, limit=2, offset=offset).json()
            for offset in (0, 2, 4)
        ]
        with soft_assertions():
            assert_ids(pages[0]["donors"], ids[:2], "the first page")
            assert_ids(pages[1]["donors"], ids[2:], "the second page")
            assert_ids(pages[2]["donors"], [], "a page past the end")
            assert_that([p["total"] for p in pages]).described_as(
                "every page should report the full total"
            ).is_equal_to([len(ids)] * len(pages))


@allure.feature("Donor list")
class TestDonorListValidation(BaseApiTest):
    @pytest.mark.parametrize(
        "params",
        [
            pytest.param([("limit", "0")], id="limit-zero"),
            pytest.param([("limit", str(DONOR_PAGE_MAX_LIMIT + 1))], id="limit-over-max"),
            pytest.param([("limit", "abc")], id="limit-not-a-number"),
            pytest.param([("offset", "-1")], id="negative-offset"),
            pytest.param([("limit", "2"), ("limit", "3")], id="repeated-limit"),
            pytest.param([("sort-by", "password_hash")], id="unknown-sort-column"),
            pytest.param([("sort-direction", "sideways")], id="unknown-sort-direction"),
            pytest.param([("status", "deleted")], id="unknown-status"),
            pytest.param([("unknown", "true")], id="unknown-parameter"),
        ],
    )
    def test_invalid_query_is_rejected(self, api: AlmaSpeiApi, params: list[tuple[str, str]]):
        # 1. List donors with an invalid query parameter
        # 2. Verification: HTTP 400 validation
        response = donors_steps.list_donors_with(api, params)
        with soft_assertions():
            assert_status(response, HTTPStatus.BAD_REQUEST, "an invalid donor query")
            assert_that(response.json().get("code")).described_as(
                "the rejection should carry the validation code"
            ).is_equal_to(ErrorCode.VALIDATION)


# --- file-local fixtures ------------------------------------------------------
@pytest.fixture
def other_tag() -> str:
    return unique_tag()


@pytest.fixture
def ordered_donors(donor_factory: DonorFactory, tag: str) -> list[dict[str, Any]]:
    """Three tagged donors whose name and city both sort Alfa < Beta < Gamma."""
    return [
        donor_factory(new_donor_profile(tag=tag).with_changes(name=f"{word} {tag}", city=word))
        for word in ORDERED_WORDS
    ]
