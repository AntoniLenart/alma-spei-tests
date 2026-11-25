"""API security tests for injection through search, filters, paths and stored text.

Request text reaches SQL only as bound parameters, and fixed maps choose the
sort column and direction. These tests send SQL metacharacters through every
donor list parameter, a donor id, and the import queue paging. Text that looks
like SQL or a spreadsheet formula must be stored as typed, as plain data. The
literal search for ``%`` and a quote probe is covered by ``test_donor_list.py``.
"""

from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.assertions import assert_error_includes
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import ErrorCode, ImportErrorPayload
from alma_spei_tests.data import DonorFactory, new_donor_profile
from alma_spei_tests.steps import donors_steps, imports_steps
from alma_spei_tests.testbase import BaseApiTest

#: Classic injection probes for a filter value.
INJECTIONS = (
    "active' OR '1'='1",
    "name; DROP TABLE donors; --",
    "1 OR 1=1",
    "asc, (SELECT pg_sleep(5))",
)

#: Text a person might type that is also SQL or a spreadsheet formula.
STORED_AS_TYPED = (
    "Robert'); DROP TABLE donors; --",
    '=HYPERLINK("http://example.invalid","kliknij")',
    "+48 600 100 200",
    "@SUM(A1:A9)",
)


@allure.feature("Security: injection")
class TestFilterInjection(BaseApiTest):
    @pytest.mark.parametrize("value", INJECTIONS)
    @pytest.mark.parametrize(
        "parameter", ["status", "entity-type", "sort-by", "sort-direction", "limit", "offset"]
    )
    def test_an_injected_donor_list_filter_is_refused(
        self, api: AlmaSpeiApi, parameter: str, value: str
    ):
        # 1. List donors with an injection probe as one filter value
        # 2. Verification: 400 validation - the value is never used as SQL
        response = donors_steps.list_donors_with(api, [(parameter, value)])
        with soft_assertions():
            assert_that(response.status_code).described_as(
                f"an injected {parameter} should be refused"
            ).is_equal_to(HTTPStatus.BAD_REQUEST)
            assert_that(response.json().get("code")).described_as(
                "the refusal should be a validation error"
            ).is_equal_to(ErrorCode.VALIDATION)

    def test_an_underscore_in_the_search_is_matched_literally(
        self, api: AlmaSpeiApi, donor: dict[str, Any], tag: str
    ):
        # 1. Create a tagged donor
        # 2. Search for the tag with its last character replaced by "_"
        # 3. Verification: nothing matches (no single-character wildcard)
        body = donors_steps.list_donors(api, search=f"{tag[:-1]}_").json()
        assert_that(body["total"]).described_as(
            "an underscore should not act as a wildcard"
        ).is_equal_to(0)

    def test_an_injected_donor_id_is_not_found(self, api: AlmaSpeiApi):
        # 1. Read a donor whose id is an injection probe
        # 2. Verification: 404 not found, never a server error or another donor
        response = api.session.get(f"/api/donors/{quote(INJECTIONS[0])}")
        assert_that(response.status_code).described_as(
            "an injected id should simply not exist"
        ).is_equal_to(HTTPStatus.NOT_FOUND)

    def test_injected_import_queue_paging_is_refused(self, api: AlmaSpeiApi):
        # 1. Read the bank review queue with an injection probe as the limit
        # 2. Verification: 400 import validation
        response = imports_steps.review_queue_with(api, [("limit", INJECTIONS[2])])
        assert_error_includes(response, HTTPStatus.BAD_REQUEST, ImportErrorPayload.VALIDATION)


@allure.feature("Security: injection")
class TestStoredAsTyped(BaseApiTest):
    @pytest.mark.parametrize("text", STORED_AS_TYPED)
    def test_sql_or_formula_text_is_stored_as_typed(
        self, api: AlmaSpeiApi, donor_factory: DonorFactory, tag: str, text: str
    ):
        # 1. Create a donor whose name is SQL- or formula-looking text
        # 2. Read it back and list the donors by the tag
        # 3. Verification: the name is exactly as typed, and the register still answers
        created = donor_factory(new_donor_profile(tag=tag).with_changes(name=f"{text} {tag}"))
        read = donors_steps.get_donor(api, created["id"]).json()["donor"]
        listed = donors_steps.list_tagged(api, tag)
        with soft_assertions():
            assert_that(read["name"]).described_as(
                "the text should be stored as plain data, exactly as typed"
            ).is_equal_to(f"{text} {tag}")
            assert_that([d["id"] for d in listed]).described_as(
                "the register should still answer normally"
            ).is_equal_to([created["id"]])
