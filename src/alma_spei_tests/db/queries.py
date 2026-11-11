"""Named database queries over ``DbClient``.

Tests and steps never write SQL; they call a method here.
"""

from alma_spei_tests.db.client import DbClient


class DbQueries:
    def __init__(self, client: DbClient):
        self.client = client
