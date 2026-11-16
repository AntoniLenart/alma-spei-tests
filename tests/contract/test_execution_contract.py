"""Contract tests: backup, outcome, history, eligibility, applied-item and capability
responses vs contracts/execution.cljc (tasks 39-40)."""

from typing import Any

import allure
from assertpy import soft_assertions

from alma_spei_tests.assertions import assert_matches_contract
from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.contracts import (
    APPLIED_ITEMS_RESPONSE,
    BACKUP_RESPONSE,
    CAPABILITIES,
    ELIGIBILITY,
    IMPORT_HISTORY,
    OUTCOME,
)
from alma_spei_tests.steps import execution_steps, review_steps
from alma_spei_tests.steps.execution_steps import CommittedImport
from alma_spei_tests.testbase import BaseContractTest


@allure.feature("Import execution contract")
class TestExecutionContract(BaseContractTest):
    def test_backup_response_matches_contract(
        self, api: AlmaSpeiApi, decided_upload: dict[str, Any]
    ):
        # 1. Request a backup receipt for a ready preview
        # 2. Verification: the body satisfies backup-response
        preview = review_steps.create_preview(api, decided_upload["batch"]["id"])
        snapshot = preview["preview"]
        body = execution_steps.request_backup(
            api, snapshot["batch-id"], snapshot["id"], execution_steps.backup_payload(preview)
        ).json()
        assert_matches_contract(body, BACKUP_RESPONSE, "backup-response")

    def test_outcomes_match_contract(self, api: AlmaSpeiApi, committed_import: CommittedImport):
        # 1. Commit a batch (fixture), then undo it
        # 2. Verification: the commit and the undo outcomes satisfy outcome
        undone = execution_steps.undo_import(api, committed_import)
        with soft_assertions():
            assert_matches_contract(committed_import.outcome, OUTCOME, "outcome (commit)")
            assert_matches_contract(undone, OUTCOME, "outcome (undo)")

    def test_reads_match_contract(self, api: AlmaSpeiApi, committed_import: CommittedImport):
        # 1. Read the history, the applied items and the undo eligibility of a committed batch
        # 2. Verification: history, items-response and eligibility
        batch_id = committed_import.batch_id
        history = execution_steps.read_history(api).json()
        items = execution_steps.read_commit_items(api, batch_id).json()
        eligibility = execution_steps.read_undo_eligibility(api, batch_id).json()
        with soft_assertions():
            assert_matches_contract(history, IMPORT_HISTORY, "history")
            assert_matches_contract(items, APPLIED_ITEMS_RESPONSE, "items-response")
            assert_matches_contract(eligibility, ELIGIBILITY, "eligibility")

    def test_capabilities_match_contract(self, api: AlmaSpeiApi):
        # 1. Read the import capabilities
        # 2. Verification: the body satisfies capabilities
        body = execution_steps.read_capabilities(api).json()
        assert_matches_contract(body, CAPABILITIES, "capabilities")
