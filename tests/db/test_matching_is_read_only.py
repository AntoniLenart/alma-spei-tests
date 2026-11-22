"""Database test: the automatic matching writes nothing canonical (task 60).

Reconciliation only records review decisions and donor proposals. Donors and
payments are written by an approved commit alone; a matched donor's profile is
never touched.
"""

from typing import Any

import allure
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import EntityType
from alma_spei_tests.data import (
    BankRow,
    BankStatement,
    new_donor_profile,
    sender_with_address,
)
from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps, imports_steps, review_steps
from alma_spei_tests.testbase import BaseDbTest


@allure.feature("Bank matching")
class TestMatchingIsReadOnly(BaseDbTest):
    def test_matching_writes_no_donor_or_payment(
        self, api: AlmaSpeiApi, db: DbQueries, donor: dict[str, Any], tag: str
    ):
        # 1. Stage an exact match for a donor and a row from an unknown identity
        # 2. Count the canonical tables and read the donor row
        # 3. Reconcile with new donors confirmed as individuals
        # 4. Verification: donors, donations and their audit are unchanged, and so is the
        #    matched donor's row
        unknown = new_donor_profile(tag=tag)
        senders = [
            sender_with_address(
                donor["name"], donor["street"], donor["postal-code"], donor["city"]
            ),
            sender_with_address(
                unknown.name, unknown.street or "", unknown.postal_code or "", unknown.city
            ),
        ]
        rows = [
            BankRow(f"2026-03-0{i + 1}", sender, f"{tag} #{i + 1}", f"{20 + i},00")
            for i, sender in enumerate(senders)
        ]
        batch = imports_steps.upload_staged(api, f"{tag}.csv", BankStatement(rows).to_csv())[
            "batch"
        ]
        before = (db_steps.read_canonical_counts(db), db_steps.read_donor(db, donor["id"]))
        review_steps.reconcile(
            api, batch["id"], review_steps.policy(new_donor_type=EntityType.INDIVIDUAL)
        )
        after = (db_steps.read_canonical_counts(db), db_steps.read_donor(db, donor["id"]))
        with soft_assertions():
            assert_that(after[0]).described_as(
                "matching should not write donors, donations or their audit"
            ).is_equal_to(before[0])
            assert_that(after[1]).described_as(
                "a matched donor's profile should stay untouched"
            ).is_equal_to(before[1])
