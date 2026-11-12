"""Database tests for the synthetic demo population loaded by ``bb seed-demo``.

The loader runs once per module against the orchestrated, disposable database
(``first_seed``), with the QA administrator as its audit actor; the tests then
inspect what it stored, run it again and try actors it must refuse. Every
profile it writes is invented and named ``DANE SYNTETYCZNE — …``.
"""

from collections import Counter
from collections.abc import Callable
from http import HTTPStatus

import allure
import pytest
from assertpy import assert_that, soft_assertions

from alma_spei_tests.clients import AlmaSpeiApi, expect_status
from alma_spei_tests.config import Settings
from alma_spei_tests.constants import AuditAction, DemoDataset, DonorStatusFilter, SeedStatus
from alma_spei_tests.data import ProvisionedAccount, new_account
from alma_spei_tests.db import DbQueries
from alma_spei_tests.orchestration import SeedResult, Stack
from alma_spei_tests.steps import db_steps, demo_steps, donors_steps
from alma_spei_tests.testbase import BaseDbTest

#: Large enough for one page holding the whole dataset.
PAGE_LIMIT = 100


@allure.feature("Synthetic demo data")
class TestSyntheticDataset(BaseDbTest):
    def test_the_first_run_loads_the_dataset(self, first_seed: SeedResult):
        # 1. Run seed-demo on the fresh database (fixture)
        # 2. Verification: it succeeds and reports the loaded dataset counts
        with soft_assertions():
            assert_that(first_seed.returncode).described_as(
                f"the first load should succeed (stderr: {first_seed.stderr[-300:]})"
            ).is_zero()
            assert_that(first_seed.summary).described_as(
                "the first load should report the whole dataset as loaded"
            ).is_equal_to(seed_summary(SeedStatus.LOADED))

    def test_profiles_are_synthetic_and_split_by_type_and_status(
        self, db: DbQueries, first_seed: SeedResult
    ):
        # 1. Read the donors carrying the synthetic name prefix
        # 2. Verification: 20 profiles at version 1 - 12 individuals, 4 businesses and
        #    4 organizations - of which 18 are active and 2 archived
        donors = db_steps.read_donors_named(db, DemoDataset.NAME_PREFIX)
        with soft_assertions():
            assert_that(len(donors)).described_as(
                "every synthetic profile should be stored"
            ).is_equal_to(DemoDataset.DONORS)
            assert_that(dict(Counter(d["entity_type"] for d in donors))).described_as(
                "the profiles should split by entity type as designed"
            ).is_equal_to(DemoDataset.ENTITY_TYPES)
            assert_that(sum(not d["is_active"] for d in donors)).described_as(
                "exactly the designed profiles should be archived"
            ).is_equal_to(DemoDataset.ARCHIVED)
            assert_that({d["version"] for d in donors}).described_as(
                "seeded profiles should never have been edited"
            ).is_equal_to({1})

    def test_payments_are_pln_in_2026_and_add_up(self, db: DbQueries, first_seed: SeedResult):
        # 1. Read the donations of the synthetic profiles
        # 2. Verification: 30 positive PLN payments dated 2026, totalling 2650 PLN
        payments = db_steps.read_donations_of_donors_named(db, DemoDataset.NAME_PREFIX)
        with soft_assertions():
            assert_that(len(payments)).described_as(
                "payments that look alike should stay separate facts"
            ).is_equal_to(DemoDataset.PAYMENTS)
            assert_that(sum(p["amount"] for p in payments)).described_as(
                "the payments should add up to the designed total"
            ).is_equal_to(DemoDataset.TOTAL)
            assert_that({p["currency"] for p in payments}).described_as(
                "every payment should be in PLN"
            ).is_equal_to({DemoDataset.CURRENCY})
            assert_that({p["received_on"].year for p in payments}).described_as(
                "every payment should be dated in 2026"
            ).is_equal_to({DemoDataset.YEAR})
            assert_that(min(p["amount"] for p in payments)).described_as(
                "every payment should be positive"
            ).is_positive()

    def test_profiles_sharing_a_full_name_stay_separate(
        self, db: DbQueries, first_seed: SeedResult
    ):
        # 1. Read the profiles carrying the shared full name
        # 2. Verification: two distinct donors at different streets, never merged
        namesakes = db_steps.read_donors_named(db, DemoDataset.SHARED_NAME)
        with soft_assertions():
            assert_that(len({d["id"] for d in namesakes})).described_as(
                "two profiles should share the full name"
            ).is_equal_to(2)
            assert_that(len({d["street"] for d in namesakes})).described_as(
                "the namesakes should live at different addresses"
            ).is_equal_to(2)

    def test_every_profile_has_its_creation_audited(self, db: DbQueries, first_seed: SeedResult):
        # 1. Read the audit actions of the synthetic profiles
        # 2. Verification: one creation entry per profile and nothing else
        actions = db_steps.read_audit_actions_of_donors_named(db, DemoDataset.NAME_PREFIX)
        assert_that(actions).described_as(
            "each synthetic profile should have exactly its creation audited"
        ).is_equal_to([AuditAction.CREATE] * DemoDataset.DONORS)

    def test_the_api_lists_only_the_active_profiles_by_default(
        self, api: AlmaSpeiApi, first_seed: SeedResult
    ):
        # 1. Search the donor list for the synthetic prefix, by default and with every status
        # 2. Verification: 18 active profiles by default, all 20 with status "all"
        prefix = DemoDataset.NAME_PREFIX.strip()
        default = list_total(api, search=prefix, limit=PAGE_LIMIT)
        everyone = list_total(api, search=prefix, limit=PAGE_LIMIT, status=DonorStatusFilter.ALL)
        assert_that((default, everyone)).described_as(
            "the API should list the active profiles by default and all of them on request"
        ).is_equal_to((DemoDataset.ACTIVE, DemoDataset.DONORS))


@allure.feature("Synthetic demo data")
class TestRepeatAndRefusals(BaseDbTest):
    def test_a_repeat_run_changes_nothing(
        self, stack: Stack, settings: Settings, db: DbQueries, first_seed: SeedResult
    ):
        # 1. Snapshot the synthetic rows
        # 2. Run seed-demo again with the same actor
        # 3. Verification: it succeeds as unchanged and every row is as before
        before = demo_snapshot(db)
        result = demo_steps.seed_demo(stack, settings.admin_username)
        with soft_assertions():
            assert_that(result.summary).described_as(
                "a repeat run should report the dataset as unchanged"
            ).is_equal_to(seed_summary(SeedStatus.UNCHANGED))
            assert_that(demo_snapshot(db)).described_as(
                "a repeat run should not insert, update or audit anything"
            ).is_equal_to(before)

    @pytest.mark.parametrize("actor", ["unknown", "staff"])
    def test_only_an_active_administrator_can_be_the_actor(
        self,
        stack: Stack,
        db: DbQueries,
        first_seed: SeedResult,
        account_factory: Callable[..., ProvisionedAccount],
        actor: str,
    ):
        # 1. Snapshot the synthetic rows
        # 2. Run seed-demo with an unknown username or a non-administrator account
        # 3. Verification: a non-zero exit with the safe refusal, and nothing changed
        username = account_factory().username if actor == "staff" else new_account().username
        before = demo_snapshot(db)
        result = demo_steps.seed_demo(stack, username)
        with soft_assertions():
            assert_that(result.returncode).described_as(
                f"an {actor} actor should be refused"
            ).is_not_zero()
            assert_that(result.stderr).described_as(
                "the refusal should name the requirement, not leak details"
            ).contains(DemoDataset.INVALID_ACTOR)
            assert_that(demo_snapshot(db)).described_as(
                "a refused run should change nothing"
            ).is_equal_to(before)


# --- file-local fixtures and helpers ------------------------------------------
@pytest.fixture(scope="module")
def first_seed(stack: Stack, settings: Settings) -> SeedResult:
    """The first seed-demo run of this module, on the disposable orchestrated database."""
    if not settings.orchestrate:
        pytest.skip("seed-demo writes demo rows; run it only against the orchestrated stack")
    return demo_steps.seed_demo(stack, settings.admin_username)


def seed_summary(status: SeedStatus) -> dict[str, str]:
    return {
        "status": status,
        "donors": str(DemoDataset.DONORS),
        "payments": str(DemoDataset.PAYMENTS),
    }


def demo_snapshot(db: DbQueries) -> tuple[list, list, list]:
    """The synthetic donors, payments and audit actions, comparable across runs."""
    prefix = DemoDataset.NAME_PREFIX
    payments = db_steps.read_donations_of_donors_named(db, prefix)
    return (
        db_steps.read_donors_named(db, prefix),
        sorted(payments, key=lambda p: (p["received_on"], p["amount"])),
        sorted(db_steps.read_audit_actions_of_donors_named(db, prefix)),
    )


def list_total(api: AlmaSpeiApi, **query: str | int) -> int:
    response = expect_status(
        donors_steps.list_donors(api, **query), HTTPStatus.OK, "List synthetic donors"
    )
    return response.json()["total"]
