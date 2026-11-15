"""Database tests for import staging (task 35): file identity, staged rows, events.

Staging is review-only: nothing reaches the canonical donor tables until a later
approval/commit step exists.
"""

from typing import Any

import allure
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import (
    BANK_MAPPING_VERSION,
    ErrorCode,
    ImportEvent,
    RowErrorCode,
    RowState,
)
from alma_spei_tests.data import BankRow, BankStatement, blank_only_csv, sha256_hex
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, imports_steps
from alma_spei_tests.testbase import BaseDbTest

#: A line whose only problem is a missing sender.
SENDERLESS_ROW = BankRow(date="2026-01-05", sender="", description="", amount="1,00")


@allure.feature("Import staging")
class TestImportStaging(BaseDbTest):
    def test_file_identity_is_its_sha256_and_size(
        self, db: DbQueries, bank_statement: BankStatement, staged_upload: dict[str, Any]
    ):
        # 1. Stage an upload (fixture)
        # 2. Read the import file by the content hash computed locally
        # 3. Verification: the file is recorded with that hash and its exact byte count
        content = bank_statement.to_csv()
        stored = db_steps.read_import_file(db, sha256_hex(content))
        with soft_assertions():
            assert_that(stored).described_as("the file should be recorded by hash").is_not_none()
            assert_that((stored or {}).get("byte_count")).described_as(
                "the recorded size should be the uploaded byte count"
            ).is_equal_to(len(content))
            assert_that((stored or {}).get("id")).described_as(
                "the batch should reference the recorded file"
            ).is_equal_to(staged_upload["batch"]["file-id"])

    def test_rows_are_staged_with_rule_version_and_codes(
        self, api: AlmaSpeiApi, db: DbQueries, bank_statement: BankStatement, tag: str
    ):
        # 1. Upload one valid line and one without a sender
        # 2. Read the staged rows from the database
        # 3. Verification: both rows stored in order, with the rule version and the error code
        statement = BankStatement([bank_statement.rows[0], SENDERLESS_ROW])
        batch = imports_steps.upload_staged(api, f"{tag}.csv", statement.to_csv())["batch"]
        rows = db_steps.read_staged_rows(db, batch["id"])
        assert_that(
            [
                (r["row_number"], r["validation_state"], r["validation_codes"], r["rule_version"])
                for r in rows
            ]
        ).described_as("staged rows should carry state, codes and the mapping version").is_equal_to(
            [
                (1, RowState.VALID, [], BANK_MAPPING_VERSION),
                (2, RowState.INVALID, [RowErrorCode.MISSING_SENDER], BANK_MAPPING_VERSION),
            ]
        )

    def test_successful_upload_records_reserved_then_staged(
        self, db: DbQueries, staged_upload: dict[str, Any]
    ):
        # 1. Stage an upload (fixture)
        # 2. Read the batch's events
        # 3. Verification: exactly reserved then staged, without reason codes
        events = db_steps.read_import_events(db, staged_upload["batch"]["id"])
        assert_that(events).described_as(
            "a staged batch should have been reserved then staged"
        ).is_equal_to([(ImportEvent.RESERVED, None), (ImportEvent.STAGED, None)])

    def test_failed_upload_records_the_failure_and_stages_nothing(
        self, api: AlmaSpeiApi, db: DbQueries, tag: str
    ):
        # 1. Upload a file without rows
        # 2. Read the batch's events and staged rows
        # 3. Verification: reserved then failed(invalid-structure), and no staged rows
        response = imports_steps.upload(api, f"{tag}.csv", blank_only_csv(tag))
        batch_id = response.json()["batch-id"]
        with soft_assertions():
            assert_that(db_steps.read_import_events(db, batch_id)).described_as(
                "a failed batch should record the failure reason"
            ).is_equal_to(
                [(ImportEvent.RESERVED, None), (ImportEvent.FAILED, ErrorCode.INVALID_STRUCTURE)]
            )
            assert_that(db_steps.read_staged_rows(db, batch_id)).described_as(
                "a failed batch should stage no rows"
            ).is_empty()

    def test_staging_leaves_the_canonical_donor_tables_untouched(
        self, api: AlmaSpeiApi, db: DbQueries, bank_statement: BankStatement, tag: str
    ):
        # 1. Count the canonical donor tables
        # 2. Stage an upload
        # 3. Verification: every canonical count is unchanged
        before = db_steps.read_canonical_counts(db)
        imports_steps.upload_staged(api, f"{tag}.csv", bank_statement.to_csv())
        assert_that(db_steps.read_canonical_counts(db)).described_as(
            "staging should not write donors, donations or their audit"
        ).is_equal_to(before)
