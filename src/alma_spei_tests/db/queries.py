"""Named database queries over ``DbClient``.

Tests and steps never write SQL; they call a method here. Everything is a read,
except the constraint probes (writes that are always rolled back, see
``DbClient.constraint_violated_by``) and one fixture-only write the app role is
granted and the API does not expose:

* ``clear_auth_throttle`` - resets login throttle buckets after a test that
                           deliberately exhausts them.
"""

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from alma_spei_tests.db.client import DbClient, Statement

#: A valid donor row for constraint probes; a probe changes single columns.
PROBE_DONOR: dict[str, object] = {
    "entity_type": "individual",
    "name": "QA schema probe",
    "city": "Testowo",
    "version": 1,
}

#: A valid donation row for constraint probes.
PROBE_DONATION: dict[str, object] = {
    "amount": "10.0000",
    "currency": "PLN",
    "received_on": "2026-01-15",
}


class DbQueries:
    def __init__(self, client: DbClient):
        self.client = client

    # --- schema: privileges and constraint probes ------------------------------
    def privileges(self, table: str, kinds: Sequence[str]) -> dict[str, bool]:
        """Which of the table privileges ``kinds`` the connected app role holds."""
        return {
            kind: self.client.scalar(
                "SELECT has_table_privilege(current_user, %s::text, %s::text)", (table, kind)
            )
            for kind in kinds
        }

    def donor_violation(self, actor_id: str, **changes: object) -> str | None:
        """The constraint a donor insert violates; ``changes`` alter a valid row."""
        return self.client.constraint_violated_by([_donor_insert(_new_id(), actor_id, changes)])

    def donation_violation(self, actor_id: str, **changes: object) -> str | None:
        """The constraint a donation of a new valid donor violates."""
        donor_id = _new_id()
        return self.client.constraint_violated_by(
            [_donor_insert(donor_id, actor_id, {}), _donation_insert(donor_id, actor_id, changes)]
        )

    def donor_audit_violation(self, actor_id: str, *, action: str, field_name: str) -> str | None:
        """The constraint violated when a new donor's audit records ``action``/``field_name``."""
        donor_id, event_id = _new_id(), _new_id()
        return self.client.constraint_violated_by(
            [
                _donor_insert(donor_id, actor_id, {}),
                (
                    "INSERT INTO donor_audit_events (id, actor_id, donor_id, action)"
                    " VALUES (%s, %s, %s, %s)",
                    (event_id, actor_id, donor_id, action),
                ),
                (
                    "INSERT INTO donor_audit_changes (event_id, field_name, before_value,"
                    " after_value) VALUES (%s, %s, 'null'::jsonb, '\"QA\"'::jsonb)",
                    (event_id, field_name),
                ),
            ]
        )

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


# --- probe statements ---------------------------------------------------------
def _new_id() -> str:
    return str(uuid.uuid4())


def _donor_insert(donor_id: str, actor_id: str, changes: Mapping[str, object]) -> Statement:
    row = {**PROBE_DONOR, "created_by": actor_id, "updated_by": actor_id, **changes}
    columns = ("entity_type", "name", "city", "version", "created_by", "updated_by")
    return (
        "INSERT INTO donors (id, entity_type, name, city, version, created_by, updated_by)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (donor_id, *(row[column] for column in columns)),
    )


def _donation_insert(donor_id: str, actor_id: str, changes: Mapping[str, object]) -> Statement:
    row = {**PROBE_DONATION, **changes}
    return (
        "INSERT INTO donations (id, donor_id, amount, currency, received_on, created_by)"
        " VALUES (%s, %s, %s::numeric, %s, %s::date, %s)",
        (_new_id(), donor_id, row["amount"], row["currency"], row["received_on"], actor_id),
    )
