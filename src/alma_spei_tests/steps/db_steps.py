"""Reusable steps for direct database checks."""

from alma_spei_tests.db import DbClient
from alma_spei_tests.steps import step


@step("Read the foundation version from application_metadata")
def read_foundation_version(db: DbClient) -> int | None:
    return db.scalar(
        "SELECT foundation_version FROM application_metadata WHERE singleton = true"
    )


@step("Count rows in application_metadata")
def count_application_metadata(db: DbClient) -> int:
    return db.scalar("SELECT count(*) FROM application_metadata")
