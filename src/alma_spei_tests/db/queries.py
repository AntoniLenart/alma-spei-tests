"""Named database queries over ``DbClient``.

Tests and steps never write SQL; they call a method here. Everything is a read,
except the constraint probes (writes that are always rolled back, see
``DbClient.constraint_violated_by``) and two fixture-only writes the app role is
granted and the API does not expose:

* ``archive_donor``      - there is no archive endpoint yet; used to build an
                           archived donor for the status filter and to keep the
                           default (active) list clean after a test;
* ``clear_auth_throttle`` - resets login throttle buckets after a test that
                           deliberately exhausts them;
* ``age_sessions``        - moves a user's sessions back in time, to check idle
                           and absolute expiry without waiting.
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

#: A valid account row for constraint probes (the other columns have defaults).
PROBE_USER: dict[str, object] = {"username": "qa.schema.probe", "display_name": "QA probe"}

#: Canonical tables a staged (unapproved) import must leave untouched.
CANONICAL_TABLES = ("donors", "donations", "donor_audit_events", "donor_audit_changes")


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

    def role_attributes(self) -> dict[str, bool]:
        """The connected app role's powerful role attributes."""
        row = self.client.query(
            "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolreplication"
            " FROM pg_roles WHERE rolname = current_user"
        )[0]
        keys = ("superuser", "create-role", "create-database", "bypass-rls", "replication")
        return dict(zip(keys, row, strict=True))

    def can_create_in_schema(self, schema: str) -> bool:
        return self.client.scalar(
            "SELECT has_schema_privilege(current_user, %s::text, 'CREATE')", (schema,)
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

    # --- authentication schema (task 57) -------------------------------------
    def tables_present(self, names: Sequence[str]) -> dict[str, bool]:
        return {
            name: self.client.scalar("SELECT to_regclass(%s) IS NOT NULL", (name,))
            for name in names
        }

    def user_violation(self, **changes: object) -> str | None:
        """The constraint a new account row violates; ``changes`` alter a valid row."""
        row = {**PROBE_USER, **changes}
        return self.client.constraint_violated_by(
            [
                (
                    "INSERT INTO users (id, username, display_name) VALUES (%s, %s, %s)",
                    (_new_id(), row["username"], row["display_name"]),
                )
            ]
        )

    def sessions_of(self, user_id: str) -> list[dict[str, Any]]:
        """The user's stored sessions, oldest first."""
        rows = self.client.query(
            "SELECT token_digest, csrf_digest, created_at, last_activity, expires_at"
            " FROM sessions WHERE user_id = %s ORDER BY created_at",
            (user_id,),
        )
        keys = ("token_digest", "csrf_digest", "created_at", "last_activity", "expires_at")
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def age_sessions(self, user_id: str, *, idle_minutes: int = 0, expired: bool = False):
        """Make the user's sessions idle for ``idle_minutes`` and/or past their expiry."""
        self.client.execute(
            "UPDATE sessions SET last_activity = now() - make_interval(mins => %s)"
            " WHERE user_id = %s",
            (idle_minutes, user_id),
        )
        if expired:
            self.client.execute(
                "UPDATE sessions SET expires_at = now() - interval '1 second' WHERE user_id = %s",
                (user_id,),
            )

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
    def donors_with_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        """The donors with these ids, by name then id."""
        rows = self.client.query(
            "SELECT id::text, name, entity_type, is_active, version, street, postal_code, city"
            " FROM donors WHERE id = ANY(%s::uuid[]) ORDER BY name, id",
            (ids,),
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

    def donations_of_donors(self, ids: list[str]) -> list[dict[str, Any]]:
        """Donations of the donors with these ids."""
        rows = self.client.query(
            "SELECT amount, currency, received_on, version FROM donations"
            " WHERE donor_id = ANY(%s::uuid[])",
            (ids,),
        )
        keys = ("amount", "currency", "received_on", "version")
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def audit_actions_of_donors(self, ids: list[str]) -> list[str]:
        """Audit actions recorded for the donors with these ids."""
        rows = self.client.query(
            "SELECT action FROM donor_audit_events WHERE donor_id = ANY(%s::uuid[])",
            (ids,),
        )
        return [row[0] for row in rows]

    # --- imports (task 35) ----------------------------------------------------
    def import_file(self, sha256: str) -> dict[str, Any] | None:
        rows = self.client.query(
            "SELECT id::text, byte_count FROM import_files WHERE file_hash_sha256 = %s", (sha256,)
        )
        return dict(zip(("id", "byte_count"), rows[0], strict=True)) if rows else None

    def import_attempts(self, sha256: str) -> int:
        """Batches (attempts) recorded for the file with this content hash."""
        return self.client.scalar(
            "SELECT count(*) FROM import_batches b JOIN import_files f ON f.id = b.file_id"
            " WHERE f.file_hash_sha256 = %s",
            (sha256,),
        )

    def import_batch_events(self, batch_id: str) -> list[tuple[str, str | None]]:
        """``(event_type, reason_code)`` of the batch, oldest first."""
        rows = self.client.query(
            "SELECT event_type, reason_code FROM import_batch_events WHERE batch_id = %s"
            " ORDER BY occurred_at, batch_version, id",
            (batch_id,),
        )
        return [(row[0], row[1]) for row in rows]

    def staged_rows(self, batch_id: str) -> list[dict[str, Any]]:
        """Staged rows of the batch in sheet order."""
        rows = self.client.query(
            "SELECT row_number, validation_state, validation_codes, rule_version,"
            " normalized_payload FROM staged_rows WHERE batch_id = %s"
            " ORDER BY worksheet_index, row_number",
            (batch_id,),
        )
        keys = ("row_number", "validation_state", "validation_codes", "rule_version", "payload")
        return [dict(zip(keys, row, strict=True)) for row in rows]

    def canonical_counts(self) -> dict[str, int]:
        """Row counts of the canonical donor tables imports must not touch yet."""
        return {
            table: self.client.scalar(f"SELECT count(*) FROM {table}")  # fixed names only
            for table in CANONICAL_TABLES
        }

    def import_batch_snapshot(self, batch_id: str) -> dict[str, int]:
        """What a read-only review must not change: version, progress, events, rows."""
        row = self.client.query(
            "SELECT b.version, b.reviewed_rows,"
            " (SELECT count(*) FROM import_batch_events e WHERE e.batch_id = b.id),"
            " (SELECT count(*) FROM staged_rows r WHERE r.batch_id = b.id)"
            " FROM import_batches b WHERE b.id = %s",
            (batch_id,),
        )[0]
        return dict(zip(("version", "reviewed_rows", "events", "staged_rows"), row, strict=True))

    # --- review decisions and previews (task 38) -------------------------------
    def review_decision(self, batch_id: str, row_number: int) -> dict[str, Any] | None:
        """The stored decision of one staged row (worksheet 1)."""
        rows = self.client.query(
            "SELECT version, kind, donor_id::text, proposal_id::text, complete,"
            " reviewer_id::text, financial->>'currency' FROM import_review_decisions"
            " WHERE batch_id = %s AND worksheet_index = 1 AND row_number = %s",
            (batch_id, row_number),
        )
        keys = ("version", "kind", "donor_id", "proposal_id", "complete", "reviewer_id", "currency")
        return dict(zip(keys, rows[0], strict=True)) if rows else None

    def review_event_types(self, batch_id: str) -> list[str]:
        """The batch's review journal, oldest first."""
        rows = self.client.query(
            "SELECT event_type FROM import_review_events WHERE batch_id = %s"
            " ORDER BY occurred_at, id",
            (batch_id,),
        )
        return [row[0] for row in rows]

    def preview_count(self, batch_id: str) -> int:
        return self.client.scalar(
            "SELECT count(*) FROM import_previews WHERE batch_id = %s", (batch_id,)
        )

    def proposal_profile(self, proposal_id: str) -> dict[str, Any] | None:
        """The stored profile JSON of a donor proposal."""
        return self.client.scalar(
            "SELECT profile FROM import_donor_proposals WHERE id = %s", (proposal_id,)
        )

    # --- commit and undo (task 39) ----------------------------------------------
    def donor_import_batch(self, donor_id: str) -> str | None:
        """The batch that created the donor (None for manual and demo donors)."""
        return self.client.scalar(
            "SELECT import_batch_id::text FROM donors WHERE id = %s", (donor_id,)
        )

    def import_attribution(self, batch_id: str) -> dict[str, int]:
        """Rows attributed to the batch: created donors, original donations, reversals."""
        row = self.client.query(
            "SELECT (SELECT count(*) FROM donors WHERE import_batch_id = %s),"
            " (SELECT count(*) FROM donations WHERE import_batch_id = %s),"
            " (SELECT count(*) FROM active_donations WHERE import_batch_id = %s),"
            " (SELECT count(*) FROM donation_reversals WHERE import_batch_id = %s)",
            (batch_id, batch_id, batch_id, batch_id),
        )[0]
        keys = ("donors", "donations", "active_donations", "reversals")
        return dict(zip(keys, row, strict=True))

    def active_catalog_counts(self) -> dict[str, int]:
        """What normal reads see: active donors and payments (reversals excluded)."""
        row = self.client.query(
            "SELECT (SELECT count(*) FROM donors WHERE is_active),"
            " (SELECT count(*) FROM active_donations)"
        )[0]
        return dict(zip(("donors", "donations"), row, strict=True))

    def catalog_revision(self) -> int:
        return self.client.scalar("SELECT revision FROM canonical_catalog_state WHERE singleton")


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
