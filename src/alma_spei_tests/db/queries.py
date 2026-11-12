"""Named database queries over ``DbClient``.

Tests and steps never write SQL; they call a method here. Everything is a read,
except the constraint probes (writes that are always rolled back, see
``DbClient.constraint_violated_by``) and two fixture-only writes the app role is
granted and the API does not expose:

* ``archive_donor``      - there is no archive endpoint yet; used to build an
                           archived donor for the status filter and to keep the
                           default (active) list clean after a test;
* ``clear_auth_throttle`` - resets login throttle buckets after a test that
                           deliberately exhausts them.
"""

import secrets
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

#: A valid first attempt of an import batch, for constraint probes.
PROBE_BATCH: dict[str, object] = {
    "attempt_number": 1,
    "retry_of": None,
    "source_type": "bank",
    "original_filename": "qa-probe.csv",
    "state": "reserved",
    "failure_code": None,
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

    def column_privileges(self, table: str, columns: Sequence[str], kind: str) -> dict[str, bool]:
        """Whether the app role holds the column privilege ``kind`` on each column."""
        return {
            column: self.client.scalar(
                "SELECT has_column_privilege(current_user, %s::text, %s::text, %s::text)",
                (table, column, kind),
            )
            for column in columns
        }

    def import_files_violation(self, *files: Mapping[str, object]) -> str | None:
        """The constraint violated when import files are recorded; each changes a valid row."""
        return self.client.constraint_violated_by(
            [_import_file_insert(_new_id(), changes) for changes in files]
        )

    def import_attempts_violation(
        self, actor_id: str, *attempts: Mapping[str, object]
    ) -> str | None:
        """The constraint violated when one new file gets these batch ``attempts``.

        Each attempt changes a valid first attempt; an integer ``retry_of`` names
        the index of an earlier attempt in the same call.
        """
        file_id = _new_id()
        batch_ids = [_new_id() for _ in attempts]
        statements = [_import_file_insert(file_id, {})]
        for batch_id, attempt in zip(batch_ids, attempts, strict=True):
            changes = dict(attempt)
            retry_of = changes.get("retry_of")
            if isinstance(retry_of, int):
                changes["retry_of"] = batch_ids[retry_of]
            statements.append(_import_batch_insert(batch_id, file_id, actor_id, changes))
        return self.client.constraint_violated_by(statements)

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

    # --- donors ---------------------------------------------------------------
    def donor(self, donor_id: str) -> dict[str, Any] | None:
        rows = self.client.query(
            "SELECT name, entity_type, city, is_active, version, created_by::text,"
            " updated_by::text FROM donors WHERE id = %s",
            (donor_id,),
        )
        if not rows:
            return None
        keys = ("name", "entity_type", "city", "is_active", "version", "created_by", "updated_by")
        return dict(zip(keys, rows[0], strict=True))

    def donor_audit_actions(self, donor_id: str) -> list[str]:
        """Audit actions recorded for the donor, oldest first."""
        rows = self.client.query(
            "SELECT action FROM donor_audit_events WHERE donor_id = %s ORDER BY occurred_at, id",
            (donor_id,),
        )
        return [row[0] for row in rows]

    def donor_audit_changed_fields(self, donor_id: str, action: str) -> set[str]:
        """Snake-case field names changed by the donor's events of one action."""
        rows = self.client.query(
            "SELECT c.field_name FROM donor_audit_changes c"
            " JOIN donor_audit_events e ON e.id = c.event_id"
            " WHERE e.donor_id = %s AND e.action = %s",
            (donor_id, action),
        )
        return {row[0] for row in rows}

    def archive_donor(self, donor_id: str):
        self.client.execute("UPDATE donors SET is_active = false WHERE id = %s", (donor_id,))

    # --- synthetic demo data ---------------------------------------------------
    def donors_named(self, prefix: str) -> list[dict[str, Any]]:
        """Donors whose name starts with ``prefix``, by name then id."""
        rows = self.client.query(
            "SELECT id::text, name, entity_type, is_active, version, street, postal_code, city"
            " FROM donors WHERE starts_with(name, %s) ORDER BY name, id",
            (prefix,),
        )
        keys = (
            "id",
            "name",
            "entity_type",
            "is_active",
            "version",
            "street",
            "postal_code",
            "city",
        )
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def donations_of_donors_named(self, prefix: str) -> list[dict[str, Any]]:
        """Donations of the donors whose name starts with ``prefix``."""
        rows = self.client.query(
            "SELECT d.amount, d.currency, d.received_on, d.version FROM donations d"
            " JOIN donors p ON p.id = d.donor_id WHERE starts_with(p.name, %s)",
            (prefix,),
        )
        keys = ("amount", "currency", "received_on", "version")
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def audit_actions_of_donors_named(self, prefix: str) -> list[str]:
        """Audit actions recorded for the donors whose name starts with ``prefix``."""
        rows = self.client.query(
            "SELECT e.action FROM donor_audit_events e JOIN donors p ON p.id = e.donor_id"
            " WHERE starts_with(p.name, %s)",
            (prefix,),
        )
        return [row[0] for row in rows]


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


def _import_file_insert(file_id: str, changes: Mapping[str, object]) -> Statement:
    row = {"file_hash_sha256": secrets.token_hex(32), "byte_count": 1, **changes}
    return (
        "INSERT INTO import_files (id, file_hash_sha256, byte_count) VALUES (%s, %s, %s)",
        (file_id, row["file_hash_sha256"], row["byte_count"]),
    )


def _import_batch_insert(
    batch_id: str, file_id: str, actor_id: str, changes: Mapping[str, object]
) -> Statement:
    row = {**PROBE_BATCH, **changes}
    columns = (
        "attempt_number",
        "retry_of",
        "source_type",
        "original_filename",
        "state",
        "failure_code",
    )
    return (
        "INSERT INTO import_batches (id, file_id, created_by, attempt_number, retry_of,"
        " source_type, original_filename, state, failure_code)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (batch_id, file_id, actor_id, *(row[column] for column in columns)),
    )
