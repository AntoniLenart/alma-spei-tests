"""psycopg-based client for direct database assertions.

Connects as the least-privileged application role (``alma_spei_app``), matching
what the backend uses. That role has SELECT on the foundation tables and no DDL
rights, which is exactly what we want for read-only verification of migrations,
constraints and seeded metadata.

The password is read from the app repo's ``.secrets/app-password`` at connect
time and never logged.
"""

from collections.abc import Sequence
from typing import Any

import psycopg

from alma_spei_tests.config import Settings


class DbClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._conn: psycopg.Connection | None = None

    def connect(self):
        s = self._settings
        self._conn = psycopg.connect(
            host=s.db_host,
            port=s.db_port,
            dbname=s.db_name,
            user=s.db_app_user,
            password=s.read_app_password(),
            connect_timeout=5,
            autocommit=True,
        )

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _require_conn(self) -> psycopg.Connection:
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        return self._conn

    def query(self, sql: str, params: Sequence[Any] | None = None) -> list[tuple]:
        """Run a read query and return all rows as tuples."""
        with self._require_conn().cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def scalar(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        """Run a query expected to yield a single row/column and return it."""
        rows = self.query(sql, params)
        if not rows:
            return None
        return rows[0][0]
