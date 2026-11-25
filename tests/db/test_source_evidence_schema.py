"""Database tests for the source evidence tables (task 64).

Migration 202611220001-source-evidence adds two append-only tables beside the
staged rows:

* ``source_observations`` - cells of a master-workbook row (yearly or monthly
  historical figures), kept as text with their source value type and an optional
  year and month, never as donations;
* ``tax_identification_evidence`` - the taxpayer and the spouse of a 1.5% tax-list
  row as separate roles, each optionally linked to a donor.

Each evidence row belongs to a staged row of a batch of the matching source
type. Constraint probes insert as the app role inside a transaction that is
always rolled back, so they leave no rows behind.
"""

from typing import Any

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.constants import Privilege
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps
from alma_spei_tests.testbase import BaseDbTest

OBSERVATIONS = "source_observations"
TAX_EVIDENCE = "tax_identification_evidence"
EVIDENCE_TABLES = (OBSERVATIONS, TAX_EVIDENCE)

#: Columns that carry what the source said (the rest identify the staged row).
OBSERVATION_COLUMNS = {
    "column_index",
    "observed_value",
    "source_value_type",
    "observed_year",
    "observed_month",
}
TAX_EVIDENCE_COLUMNS = {"subject_role", "donor_id", "tax_year"}

#: The batch source types (``import_batches.source_type``).
MASTER, TAX, BANK = "master", "tax", "bank"

#: Both roles of one tax-list row.
TAXPAYER = {"subject_role": "taxpayer"}
SPOUSE = {"subject_role": "spouse"}

#: A donor id that exists nowhere.
UNKNOWN_DONOR = "00000000-0000-4000-8000-000000000000"


@allure.feature("Source evidence schema")
class TestSourceEvidenceTables(BaseDbTest):
    def test_the_migration_creates_both_tables_with_their_evidence_columns(self, db: DbQueries):
        # 1. Read which evidence tables exist and their columns
        # 2. Verification: both tables exist and carry the source's value, type, year and
        #    month, and the tax role, donor link and tax year
        with soft_assertions():
            assert_that(db_steps.read_tables_present(db, EVIDENCE_TABLES)).described_as(
                "the migration should create both evidence tables"
            ).is_equal_to(dict.fromkeys(EVIDENCE_TABLES, True))
            assert_that(db_steps.read_columns(db, OBSERVATIONS)).described_as(
                "an observation should keep the source cell's value, type, year and month"
            ).contains(*OBSERVATION_COLUMNS)
            assert_that(db_steps.read_columns(db, TAX_EVIDENCE)).described_as(
                "tax evidence should keep the role, the donor link and the tax year"
            ).contains(*TAX_EVIDENCE_COLUMNS)

    def test_observations_stay_apart_from_the_donations(self, db: DbQueries):
        # 1. Read what the observations reference and which triggers they fire
        # 2. Verification: only the import batch and its staged row are referenced, and no
        #    trigger turns an observation into a payment
        with soft_assertions():
            assert_that(db_steps.read_foreign_key_targets(db, OBSERVATIONS)).described_as(
                "observations should belong to the import, not to donors or donations"
            ).is_equal_to({"import_batches", "staged_rows"})
            assert_that(db_steps.read_triggers(db, OBSERVATIONS)).described_as(
                "nothing should create a donation from an observation"
            ).is_empty()

    def test_tax_evidence_belongs_to_the_import_and_may_name_a_donor(self, db: DbQueries):
        # 1. Read what the tax evidence references
        # 2. Verification: its import batch, its staged row and, optionally, a donor
        assert_that(db_steps.read_foreign_key_targets(db, TAX_EVIDENCE)).described_as(
            "tax evidence should reference its import and may link a donor"
        ).is_equal_to({"import_batches", "staged_rows", "donors"})


@allure.feature("Source evidence schema")
class TestObservationConstraints(BaseDbTest):
    def test_a_valid_observation_of_a_master_row_is_accepted(self, db: DbQueries, admin_id: str):
        # 1. Record a yearly and a monthly observation of a master-workbook row (rolled back)
        # 2. Verification: nothing is rejected, so each negative probe below tests one rule
        monthly = {"column_index": 8, "observed_month": 3}
        assert_that(
            db_steps.probe_source_evidence(db, admin_id, MASTER, observations=[{}, monthly])
        ).described_as("valid observations of a master row should be accepted").is_none()

    @pytest.mark.parametrize(
        ("changes", "constraint"),
        [
            pytest.param(
                {"column_index": 0}, "source_observations_column_index_check", id="column"
            ),
            pytest.param(
                {"observed_value": "   "}, "source_observations_observed_value_check", id="blank"
            ),
            pytest.param(
                {"source_value_type": "date"},
                "source_observations_source_value_type_check",
                id="value-type",
            ),
            pytest.param(
                {"observed_month": 13}, "source_observations_observed_month_check", id="month"
            ),
            pytest.param(
                {"row_number": 2},
                "source_observations_batch_id_worksheet_index_row_number_fkey",
                id="no-staged-row",
            ),
        ],
    )
    def test_an_observation_records_one_real_source_cell(
        self, db: DbQueries, admin_id: str, changes: dict[str, Any], constraint: str
    ):
        # 1. Record an observation that breaks one rule (rolled back)
        # 2. Verification: the database rejects it with that rule's constraint
        assert_that(
            db_steps.probe_source_evidence(db, admin_id, MASTER, observations=[changes])
        ).described_as(f"an observation with {changes} should violate {constraint}").is_equal_to(
            constraint
        )

    def test_a_cell_is_observed_once(self, db: DbQueries, admin_id: str):
        # 1. Record the same cell of a master row twice (rolled back)
        # 2. Verification: the second observation is rejected
        assert_that(
            db_steps.probe_source_evidence(db, admin_id, MASTER, observations=[{}, {}])
        ).described_as("a source cell should be observed once").is_equal_to(
            "source_observations_pkey"
        )

    @pytest.mark.parametrize("source_type", [TAX, BANK])
    def test_only_a_master_batch_has_observations(
        self, db: DbQueries, admin_id: str, source_type: str
    ):
        # 1. Record an observation of a row of a tax or bank batch (rolled back)
        # 2. Verification: the batch's source type does not match
        assert_that(
            db_steps.probe_source_evidence(db, admin_id, source_type, observations=[{}])
        ).described_as(f"a {source_type} batch should have no observations").is_equal_to(
            "source_observations_batch_id_source_type_fkey"
        )


@allure.feature("Source evidence schema")
class TestTaxEvidenceConstraints(BaseDbTest):
    def test_the_taxpayer_and_the_spouse_are_recorded_separately(
        self, db: DbQueries, admin_id: str
    ):
        # 1. Record both roles of one tax-list row, the taxpayer linked to a donor (rolled back)
        # 2. Verification: nothing is rejected
        assert_that(
            db_steps.probe_source_evidence(
                db, admin_id, TAX, tax_roles=[TAXPAYER | {"donor_id": True}, SPOUSE]
            )
        ).described_as("the taxpayer and the spouse should be two separate roles").is_none()

    @pytest.mark.parametrize(
        ("roles", "constraint"),
        [
            pytest.param(
                [{"subject_role": "household"}],
                "tax_identification_evidence_subject_role_check",
                id="other-role",
            ),
            pytest.param(
                [TAXPAYER, TAXPAYER], "tax_identification_evidence_pkey", id="same-role-twice"
            ),
            pytest.param(
                [TAXPAYER | {"donor_id": UNKNOWN_DONOR}],
                "tax_identification_evidence_donor_id_fkey",
                id="unknown-donor",
            ),
            pytest.param(
                [TAXPAYER | {"row_number": 2}],
                # PostgreSQL cuts generated names to 63 characters
                "tax_identification_evidence_batch_id_worksheet_index_row_n_fkey",
                id="no-staged-row",
            ),
        ],
    )
    def test_a_role_is_one_person_of_one_real_row(
        self, db: DbQueries, admin_id: str, roles: list[dict[str, Any]], constraint: str
    ):
        # 1. Record tax roles that break one rule (rolled back)
        # 2. Verification: the database rejects them with that rule's constraint
        assert_that(
            db_steps.probe_source_evidence(db, admin_id, TAX, tax_roles=roles)
        ).described_as(f"tax roles {roles} should violate {constraint}").is_equal_to(constraint)

    @pytest.mark.parametrize("source_type", [MASTER, BANK])
    def test_only_a_tax_batch_has_tax_evidence(
        self, db: DbQueries, admin_id: str, source_type: str
    ):
        # 1. Record a tax role of a row of a master or bank batch (rolled back)
        # 2. Verification: the batch's source type does not match
        assert_that(
            db_steps.probe_source_evidence(db, admin_id, source_type, tax_roles=[TAXPAYER])
        ).described_as(f"a {source_type} batch should have no tax evidence").is_equal_to(
            "tax_identification_evidence_batch_id_source_type_fkey"
        )


@allure.feature("Source evidence schema")
class TestSourceEvidenceGrants(BaseDbTest):
    @pytest.mark.parametrize("table", EVIDENCE_TABLES)
    def test_evidence_is_append_only_for_the_app_role(self, db: DbQueries, table: str):
        # 1. Read the app role's privileges on the evidence table
        # 2. Verification: it may read and insert, but never change, delete or truncate
        privileges = db_steps.read_privileges(db, table, tuple(Privilege))
        assert_that(privileges).described_as(
            f"{table} should only be read and appended by the application"
        ).is_equal_to(
            {
                Privilege.SELECT: True,
                Privilege.INSERT: True,
                Privilege.UPDATE: False,
                Privilege.DELETE: False,
                Privilege.TRUNCATE: False,
            }
        )
