"""Database test: reviewing (queue, batch, comparison) writes nothing (task 37)."""

from typing import Any

import allure
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, imports_steps
from alma_spei_tests.testbase import BaseDbTest


@allure.feature("Import review")
class TestReviewIsReadOnly(BaseDbTest):
    def test_browsing_and_comparing_change_nothing(
        self, api: AlmaSpeiApi, db: DbQueries, staged_upload: dict[str, Any], donor: dict[str, Any]
    ):
        # 1. Snapshot the staged batch and the canonical donor tables
        # 2. Read the queue and the batch, and compare both rows with a donor
        # 3. Verification: batch version, progress, events, staged rows and donor tables unchanged
        batch_id = staged_upload["batch"]["id"]
        before = (db_steps.snapshot_import_batch(db, batch_id), db_steps.read_canonical_counts(db))
        imports_steps.review_queue(api)
        imports_steps.read_batch(api, batch_id)
        for row in (1, 2):
            imports_steps.compare(api, batch_id, 1, row, donor["id"])
        after = (db_steps.snapshot_import_batch(db, batch_id), db_steps.read_canonical_counts(db))
        with soft_assertions():
            assert_that(after[0]).described_as(
                "reviewing should not change the batch, its events or rows"
            ).is_equal_to(before[0])
            assert_that(after[1]).described_as(
                "reviewing should not write donors, donations or their audit"
            ).is_equal_to(before[1])
