"""Named database queries over ``DbClient``.

Tests and steps never write SQL; they call a method here. Everything is a read,
except one fixture-only write the app role is granted and the API does not
expose:

* ``clear_auth_throttle`` - resets login throttle buckets after a test that
                           deliberately exhausts them.
"""

from typing import Any

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

    # --- accounts & sessions --------------------------------------------------
    def user(self, username: str) -> dict[str, Any] | None:
        rows = self.client.query(
            "SELECT u.id::text, u.username, u.display_name, u.active, u.administrator,"
            " c.password_hash, c.password_change_required"
            " FROM users u LEFT JOIN local_credentials c ON c.user_id = u.id"
            " WHERE u.username = %s",
            (username,),
        )
        if not rows:
            return None
        keys = (
            "id",
            "username",
            "display_name",
            "active",
            "administrator",
            "password_hash",
            "password_change_required",
        )
        return dict(zip(keys, rows[0], strict=True))

    def session_count(self, user_id: str) -> int:
        return self.client.scalar("SELECT count(*) FROM sessions WHERE user_id = %s", (user_id,))

    def security_event_types(self, user_id: str) -> list[str]:
        """Event types targeting the user, oldest first."""
        rows = self.client.query(
            "SELECT event_type FROM security_audit_events WHERE target_id = %s"
            " ORDER BY occurred_at, id",
            (user_id,),
        )
        return [row[0] for row in rows]

    def security_events_mentioning(self, text: str) -> int:
        """Security audit rows whose ``changes`` payload contains ``text``."""
        return self.client.scalar(
            "SELECT count(*) FROM security_audit_events WHERE strpos(changes::text, %s) > 0",
            (text,),
        )

    def clear_auth_throttle(self):
        self.client.execute("DELETE FROM auth_throttle_buckets")
