"""Contract tests: import responses vs contracts/imports.cljc (task 35)."""

from http import HTTPStatus
from typing import Any

import allure

from alma_spei_tests.assertions import assert_matches_contract, assert_status
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.contracts import BATCH, ROWS_RESPONSE, UPLOAD_RESPONSE
from alma_spei_tests.data import BankRow, BankStatement, blank_only_csv
from alma_spei_tests.steps import imports_steps
from alma_spei_tests.testbase import BaseContractTest


@allure.feature("Import contract")
class TestImportContract(BaseContractTest):
    def test_upload_response_matches_contract(
        self, api: AlmaSpeiApi, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload a statement with one valid and one invalid line
        # 2. Verification: the 201 body satisfies upload-response
        statement = BankStatement([bank_statement.rows[0], BankRow("bad-date", "", "", "x")])
        body = imports_steps.upload_staged(api, f"{tag}.csv", statement.to_csv())
        assert_matches_contract(body, UPLOAD_RESPONSE, "upload-response")

    def test_rows_response_matches_contract(self, api: AlmaSpeiApi, staged_upload: dict[str, Any]):
        # 1. Read the staged rows of an upload
        # 2. Verification: the body satisfies rows-response
        body = imports_steps.read_rows(api, staged_upload["batch"]["id"]).json()
        assert_matches_contract(body, ROWS_RESPONSE, "rows-response")

    def test_failed_batch_in_a_rejection_matches_contract(self, api: AlmaSpeiApi, tag: str):
        # 1. Upload a file without rows
        # 2. Verification: the rejection's failed batch satisfies the batch schema
        response = imports_steps.upload(api, f"{tag}.csv", blank_only_csv(tag))
        assert_status(response, HTTPStatus.BAD_REQUEST, "uploading a file without rows")
        assert_matches_contract(response.json().get("batch"), BATCH, "batch")
