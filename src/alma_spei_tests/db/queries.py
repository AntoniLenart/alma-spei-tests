"""Named database queries over ``DbClient``.

Tests and steps never write SQL; they call a method here.
"""

from alma_spei_tests.db.client import DbClient


class DbQueries:
    def __init__(self, client: DbClient):
        self.client = client

    # --- foundation -----------------------------------------------------------
    def foundation_version(self) -> int | None:
        return self.client.scalar(
            "SELECT foundation_version FROM application_metadata WHERE singleton = true"
        )

    def application_metadata_rows(self) -> int:
        return self.client.scalar("SELECT count(*) FROM application_metadata")
