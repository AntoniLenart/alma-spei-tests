"""Database security tests: the application connects with a least-privileged role.

If the backend were ever tricked into running SQL it should not, the damage is
bounded by the ``alma_spei_app`` role: it is no superuser, cannot create roles or
databases, cannot bypass row security or replicate, and cannot create objects in
the schema. Table-level grants are checked by each schema's own tests.
"""

import allure
from assertpy import assert_that, soft_assertions

from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import db_steps
from alma_spei_tests.testbase import BaseDbTest

#: The schema holding the application's tables.
APP_SCHEMA = "public"


@allure.feature("Security: database role")
class TestApplicationRole(BaseDbTest):
    def test_the_app_role_has_no_administrative_power(self, db: DbQueries):
        # 1. Read the connected app role's attributes and its schema privilege
        # 2. Verification: none of the powerful attributes, and no CREATE in the schema
        with soft_assertions():
            assert_that(db_steps.read_role_attributes(db)).described_as(
                "the app role should hold no administrative attribute"
            ).is_equal_to(
                {
                    "superuser": False,
                    "create-role": False,
                    "create-database": False,
                    "bypass-rls": False,
                    "replication": False,
                }
            )
            assert_that(db_steps.read_can_create_in_schema(db, APP_SCHEMA)).described_as(
                "the app role should not create tables or functions"
            ).is_false()
