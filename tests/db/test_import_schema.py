"""Database tests for the import foundation schema: constraints and the app role's grants.

Migration 202611070002-import-foundation creates import files (identified by
their SHA-256), the batches (attempts) per file, batch events and staged rows.
Constraint probes insert as the app role inside a transaction that is always
rolled back, so they leave no rows behind.
"""

from typing import Any

import allure
import pytest
from assertpy import assert_that

from alma_spei_tests.constants import Privilege
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps
from alma_spei_tests.testbase import BaseDbTest

IMPORT_TABLES = ("import_files", "import_batches", "import_batch_events", "staged_rows")

#: A well-formed content hash (64 lowercase hex digits) shared by two probe files.
SAME_HASH = "ab" * 32

#: A batch that failed its first attempt, so a retry may follow it.
FAILED_FIRST_ATTEMPT = {"state": "failed", "failure_code": "parse-failed"}

#: A second attempt retrying the first attempt of the same call.
RETRY_OF_FIRST = {"attempt_number": 2, "retry_of": 0}

#: The only import_files column the app role may update.
FILE_UPDATABLE = ("last_attempt_at",)
FILE_FIXED = ("id", "file_hash_sha256", "byte_count", "created_at")

#: import_batches columns the app role may update while a batch moves on.
BATCH_UPDATABLE = ("updated_at", "version", "state", "failure_code", "total_rows", "valid_rows")
#: import_batches columns that identify the batch and never change.
BATCH_FIXED = ("id", "file_id", "attempt_number", "retry_of", "source_type", "original_filename")


@allure.feature("Import schema")
class TestImportFileConstraints(BaseDbTest):
    def test_a_valid_file_with_a_first_attempt_is_accepted(self, db: DbQueries, admin_id: str):
        # 1. Record a file and its first attempt as the app role (rolled back)
        # 2. Verification: nothing is rejected, so each negative probe below tests one rule
        assert_that(db_steps.probe_import_attempts(db, admin_id, {})).described_as(
            "a valid file with a first attempt should satisfy every constraint"
        ).is_none()

    @pytest.mark.parametrize(
        ("changes", "constraint"),
        [
            pytest.param(
                {"file_hash_sha256": "AB" * 32},
                "import_files_file_hash_sha256_check",
                id="upper-case-hash",
            ),
            pytest.param(
                {"file_hash_sha256": "a" * 63},
                "import_files_file_hash_sha256_check",
                id="short-hash",
            ),
            pytest.param({"byte_count": 0}, "import_files_byte_count_check", id="empty-file"),
        ],
    )
    def test_a_file_is_identified_by_a_sha256_of_its_bytes(
        self, db: DbQueries, changes: dict[str, Any], constraint: str
    ):
        # 1. Record a file whose identity breaks one rule (rolled back)
        # 2. Verification: the database rejects it with that rule's constraint
        assert_that(db_steps.probe_import_files(db, changes)).described_as(
            f"an import file with {changes} should violate {constraint}"
        ).is_equal_to(constraint)

    def test_the_same_content_is_recorded_once(self, db: DbQueries):
        # 1. Record two files with the same content hash (rolled back)
        # 2. Verification: the second one is rejected by the unique hash
        assert_that(
            db_steps.probe_import_files(
                db, {"file_hash_sha256": SAME_HASH}, {"file_hash_sha256": SAME_HASH}
            )
        ).described_as("a content hash should identify one file").is_equal_to(
            "import_files_file_hash_sha256_key"
        )


@allure.feature("Import schema")
class TestImportBatchConstraints(BaseDbTest):
    @pytest.mark.parametrize(
        ("changes", "constraint"),
        [
            pytest.param({"source_type": "csv"}, "import_batches_source_type_check", id="source"),
            pytest.param(
                {"original_filename": "statements/2026.csv"},
                "import_batches_original_filename_check",
                id="path-in-name",
            ),
            pytest.param(
                {"original_filename": ".."},
                "import_batches_original_filename_check",
                id="dot-dot-name",
            ),
            pytest.param({"state": "done"}, "import_batches_state_check", id="unknown-state"),
            pytest.param(
                {"state": "failed", "failure_code": "oops"},
                "import_batches_failure_code_check",
                id="unknown-failure-code",
            ),
        ],
    )
    def test_an_invalid_batch_is_rejected(
        self, db: DbQueries, admin_id: str, changes: dict[str, Any], constraint: str
    ):
        # 1. Record a file with a first attempt that breaks one rule (rolled back)
        # 2. Verification: the database rejects it with that rule's constraint
        assert_that(db_steps.probe_import_attempts(db, admin_id, changes)).described_as(
            f"a batch with {changes} should violate {constraint}"
        ).is_equal_to(constraint)

    def test_a_failed_attempt_can_be_retried(self, db: DbQueries, admin_id: str):
        # 1. Record a failed first attempt and a second attempt retrying it (rolled back)
        # 2. Verification: nothing is rejected
        assert_that(
            db_steps.probe_import_attempts(db, admin_id, FAILED_FIRST_ATTEMPT, RETRY_OF_FIRST)
        ).described_as("a retry of a failed attempt should be accepted").is_none()

    def test_a_file_has_at_most_one_pending_attempt(self, db: DbQueries, admin_id: str):
        # 1. Record a pending first attempt and a pending retry of it (rolled back)
        # 2. Verification: the second pending attempt is rejected
        assert_that(db_steps.probe_import_attempts(db, admin_id, {}, RETRY_OF_FIRST)).described_as(
            "a file should never have two pending attempts"
        ).is_equal_to("import_batches_one_pending")

    def test_attempt_numbers_are_unique_per_file(self, db: DbQueries, admin_id: str):
        # 1. Record a failed first attempt and another first attempt of the same file
        # 2. Verification: the duplicate attempt number is rejected
        assert_that(
            db_steps.probe_import_attempts(db, admin_id, FAILED_FIRST_ATTEMPT, {})
        ).described_as("a file should number its attempts once each").is_equal_to(
            "import_batches_file_id_attempt_number_key"
        )


@allure.feature("Import schema")
class TestImportGrants(BaseDbTest):
    @pytest.mark.parametrize("table", IMPORT_TABLES)
    def test_import_records_are_never_deleted(self, db: DbQueries, table: str):
        # 1. Read the app role's privileges on the import table
        # 2. Verification: it may read and insert, but neither delete nor truncate
        privileges = db_steps.read_privileges(
            db, table, (Privilege.SELECT, Privilege.INSERT, Privilege.DELETE, Privilege.TRUNCATE)
        )
        assert_that(privileges).described_as(
            f"{table} rows should be kept for the import history"
        ).is_equal_to(
            {
                Privilege.SELECT: True,
                Privilege.INSERT: True,
                Privilege.DELETE: False,
                Privilege.TRUNCATE: False,
            }
        )

    @pytest.mark.parametrize("table", ["import_batch_events", "staged_rows"])
    def test_events_and_staged_rows_are_append_only(self, db: DbQueries, table: str):
        # 1. Read the app role's update privilege on the table
        # 2. Verification: no row can be changed once written
        assert_that(db_steps.read_privileges(db, table, (Privilege.UPDATE,))).described_as(
            f"{table} should be append-only"
        ).is_equal_to({Privilege.UPDATE: False})

    def test_only_the_attempt_time_of_a_file_changes(self, db: DbQueries):
        # 1. Read the app role's column update privileges on import_files
        # 2. Verification: only last_attempt_at is updatable
        columns = FILE_UPDATABLE + FILE_FIXED
        assert_that(
            db_steps.read_column_privileges(db, "import_files", columns, Privilege.UPDATE)
        ).described_as("a file's identity should never change").is_equal_to(
            {column: column in FILE_UPDATABLE for column in columns}
        )

    def test_a_batch_changes_state_but_never_identity(self, db: DbQueries):
        # 1. Read the app role's column update privileges on import_batches
        # 2. Verification: the progress columns are updatable, the identifying ones are not
        columns = BATCH_UPDATABLE + BATCH_FIXED
        assert_that(
            db_steps.read_column_privileges(db, "import_batches", columns, Privilege.UPDATE)
        ).described_as("a batch should move on without changing what it is").is_equal_to(
            {column: column in BATCH_UPDATABLE for column in columns}
        )
