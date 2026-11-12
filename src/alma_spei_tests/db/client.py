"""psycopg-based client for direct database assertions.

Connects as the least-privileged application role (``alma_spei_app``), matching
what the backend uses. That role has SELECT on the foundation tables and no DDL
rights, which is exactly what we want for read-only verification of migrations,
constraints and seeded metadata. Constraint probes write inside a transaction
that is always rolled back (``constraint_violated_by``), so they leave nothing.

The password is read from the app repo's ``.secrets/app-password`` at connect
time and never logged. Named queries live in ``db/queries.py``.
"""

from collections.abc import Sequence
from typing import Any

import psycopg

from alma_spei_tests.config import Settings

#: One SQL statement with its parameters.
Statement = tuple[str, Sequence[Any]]


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

    def execute(self, sql: str, params: Sequence[Any] | None = None):
        """Run a statement that returns no rows (fixture-only writes)."""
        with self._require_conn().cursor() as cur:
            cur.execute(sql, params)

    def constraint_violated_by(self, statements: Sequence[Statement]) -> str | None:
        """Run the writes in one transaction that is always rolled back.

        Returns the name of the constraint the database enforced (the SQLSTATE
        when it names none), or None when it accepted every statement.
        """
        conn = self._require_conn()
        try:
            with conn.transaction(force_rollback=True), conn.cursor() as cur:
                for sql, params in statements:
                    cur.execute(sql, params)
        except psycopg.errors.IntegrityError as exc:
            return exc.diag.constraint_name or exc.sqlstate
        return None
