"""Reusable steps for direct database checks."""

from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import step


@step("Read the foundation version from application_metadata")
def read_foundation_version(db: DbQueries) -> int | None:
    return db.foundation_version()


@step("Count rows in application_metadata")
def count_application_metadata(db: DbQueries) -> int:
    return db.application_metadata_rows()
