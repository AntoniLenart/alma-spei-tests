"""Database tests for the foundation migration.

Migration 202610250001-foundation creates a singleton ``application_metadata``
row with ``foundation_version = 1`` and grants SELECT to ``alma_spei_app``.
These tests connect as that least-privileged role and verify the seeded state.
"""

import allure
import pytest
from assertpy import assert_that

from alma_spei_tests.constants import FOUNDATION_VERSION, SINGLETON_ROW_COUNT
from alma_spei_tests.db import DbClient
from alma_spei_tests.steps import db_steps
from alma_spei_tests.testbase import BaseDbTest


@allure.feature("Foundation migration")
class TestApplicationMetadata(BaseDbTest):
    @pytest.mark.smoke
    def test_foundation_version_is_the_expected_version(self, db: DbClient):
        # 1. Read the foundation version seeded by the migration
        # 2. Verification: the seeded version equals the expected foundation version
        version = db_steps.read_foundation_version(db)
        assert_that(version).described_as(
            "migration should seed the expected foundation version"
        ).is_equal_to(FOUNDATION_VERSION)

    def test_application_metadata_is_singleton(self, db: DbClient):
        # 1. Count the rows in application_metadata
        # 2. Verification: the table holds exactly one row
        count = db_steps.count_application_metadata(db)
        assert_that(count).described_as(
            "application_metadata should be a singleton table"
        ).is_equal_to(SINGLETON_ROW_COUNT)
