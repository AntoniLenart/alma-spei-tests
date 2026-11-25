"""Reusable steps for direct database checks."""

from collections.abc import Mapping, Sequence
from typing import Any

from alma_spei_tests.db import DbQueries
from alma_spei_tests.steps import step


def _existing(row: dict[str, Any] | None, what: str) -> dict[str, Any]:
    """The row a step expects to exist; fails clearly when the lookup found none."""
    if row is None:
        raise AssertionError(f"{what} should exist in the database")
    return row


@step("Read the foundation version from application_metadata")
def read_foundation_version(db: DbQueries) -> int | None:
    return db.foundation_version()


@step("Count rows in application_metadata")
def count_application_metadata(db: DbQueries) -> int:
    return db.application_metadata_rows()


@step("Read user {username} with its local credential")
def read_user(db: DbQueries, username: str) -> dict[str, Any]:
    return _existing(db.user(username), f"user {username}")


@step("Count live sessions of user {user_id}")
def count_sessions(db: DbQueries, user_id: str) -> int:
    return db.session_count(user_id)


@step("Read security audit events targeting user {user_id}")
def read_security_events(db: DbQueries, user_id: str) -> list[str]:
    return db.security_event_types(user_id)


@step("Count security audit rows mentioning a secret")
def count_security_events_mentioning(db: DbQueries, text: str) -> int:
    return db.security_events_mentioning(text)


@step("Check which of the tables {names} exist")
def read_tables_present(db: DbQueries, names: Sequence[str]) -> dict[str, bool]:
    return db.tables_present(names)


@step("Probe an account row with {changes} (rolled back)")
def probe_user(db: DbQueries, **changes: object) -> str | None:
    return db.user_violation(**changes)


@step("Read the stored sessions of user {user_id}")
def read_sessions(db: DbQueries, user_id: str) -> list[dict[str, Any]]:
    return db.sessions_of(user_id)


@step("Age the sessions of user {user_id} (idle {idle_minutes} min, expired {expired})")
def age_sessions(db: DbQueries, user_id: str, *, idle_minutes: int = 0, expired: bool = False):
    db.age_sessions(user_id, idle_minutes=idle_minutes, expired=expired)


@step("Read donor row {donor_id}")
def read_donor(db: DbQueries, donor_id: str) -> dict[str, Any]:
    return _existing(db.donor(donor_id), f"donor {donor_id}")


@step("Read audit actions of donor {donor_id}")
def read_donor_audit_actions(db: DbQueries, donor_id: str) -> list[str]:
    return db.donor_audit_actions(donor_id)


@step("Read fields changed by '{action}' events of donor {donor_id}")
def read_donor_changed_fields(db: DbQueries, donor_id: str, action: str) -> set[str]:
    return db.donor_audit_changed_fields(donor_id, action)


@step("Archive donor {donor_id} directly in the database")
def archive_donor(db: DbQueries, donor_id: str):
    db.archive_donor(donor_id)


@step("Read the app role's {kinds} privileges on {table}")
def read_privileges(db: DbQueries, table: str, kinds: Sequence[str]) -> dict[str, bool]:
    return db.privileges(table, kinds)


@step("Probe a donor row with {changes} (rolled back)")
def probe_donor(db: DbQueries, actor_id: str, **changes: object) -> str | None:
    return db.donor_violation(actor_id, **changes)


@step("Probe a donation with {changes} (rolled back)")
def probe_donation(db: DbQueries, actor_id: str, **changes: object) -> str | None:
    return db.donation_violation(actor_id, **changes)


@step("Probe a donor audit '{action}' event changing '{field_name}' (rolled back)")
def probe_donor_audit(db: DbQueries, actor_id: str, action: str, field_name: str) -> str | None:
    return db.donor_audit_violation(actor_id, action=action, field_name=field_name)


@step("Read the app role's {kind} privilege on columns {columns} of {table}")
def read_column_privileges(
    db: DbQueries, table: str, columns: Sequence[str], kind: str
) -> dict[str, bool]:
    return db.column_privileges(table, columns, kind)


@step("Probe import files {files} (rolled back)")
def probe_import_files(db: DbQueries, *files: Mapping[str, object]) -> str | None:
    return db.import_files_violation(*files)


@step("Probe source evidence of a {source_type} batch (rolled back)")
def probe_source_evidence(
    db: DbQueries,
    actor_id: str,
    source_type: str,
    *,
    observations: Sequence[Mapping[str, object]] = (),
    tax_roles: Sequence[Mapping[str, object]] = (),
) -> str | None:
    return db.source_evidence_violation(
        actor_id, source_type, observations=observations, tax_roles=tax_roles
    )


@step("Read the tables referenced by {table}")
def read_foreign_key_targets(db: DbQueries, table: str) -> set[str]:
    return db.foreign_key_targets(table)


@step("Read the triggers on {table}")
def read_triggers(db: DbQueries, table: str) -> list[str]:
    return db.triggers_on(table)


@step("Read the columns of {table}")
def read_columns(db: DbQueries, table: str) -> set[str]:
    return db.column_names(table)


@step("Probe import attempts {attempts} of one file (rolled back)")
def probe_import_attempts(
    db: DbQueries, actor_id: str, *attempts: Mapping[str, object]
) -> str | None:
    return db.import_attempts_violation(actor_id, *attempts)


@step("Read the donors with {ids}")
def read_donors_with_ids(db: DbQueries, ids: list[str]) -> list[dict[str, Any]]:
    return db.donors_with_ids(ids)


@step("Read the donations of the donors with {ids}")
def read_donations_of_donors(db: DbQueries, ids: list[str]) -> list[dict[str, Any]]:
    return db.donations_of_donors(ids)


@step("Read the audit actions of the donors with {ids}")
def read_audit_actions_of_donors(db: DbQueries, ids: list[str]) -> list[str]:
    return db.audit_actions_of_donors(ids)


@step("Read the import file with hash {sha256}")
def read_import_file(db: DbQueries, sha256: str) -> dict[str, Any] | None:
    return db.import_file(sha256)


@step("Count import attempts of the file with hash {sha256}")
def count_import_attempts(db: DbQueries, sha256: str) -> int:
    return db.import_attempts(sha256)


@step("Read the events of import batch {batch_id}")
def read_import_events(db: DbQueries, batch_id: str) -> list[tuple[str, str | None]]:
    return db.import_batch_events(batch_id)


@step("Read the staged rows of import batch {batch_id}")
def read_staged_rows(db: DbQueries, batch_id: str) -> list[dict[str, Any]]:
    return db.staged_rows(batch_id)


@step("Count rows in the canonical donor tables")
def read_canonical_counts(db: DbQueries) -> dict[str, int]:
    return db.canonical_counts()


@step("Snapshot import batch {batch_id} (version, progress, events, rows)")
def snapshot_import_batch(db: DbQueries, batch_id: str) -> dict[str, int]:
    return db.import_batch_snapshot(batch_id)


@step("Read the stored decision of row {row_number} of import batch {batch_id}")
def read_review_decision(db: DbQueries, batch_id: str, row_number: int) -> dict[str, Any]:
    return _existing(db.review_decision(batch_id, row_number), f"decision of row {row_number}")


@step("Read the review journal of import batch {batch_id}")
def read_review_events(db: DbQueries, batch_id: str) -> list[str]:
    return db.review_event_types(batch_id)


@step("Count the previews of import batch {batch_id}")
def count_previews(db: DbQueries, batch_id: str) -> int:
    return db.preview_count(batch_id)


@step("Read the stored profile of donor proposal {proposal_id}")
def read_proposal_profile(db: DbQueries, proposal_id: str) -> dict[str, Any]:
    return _existing(db.proposal_profile(proposal_id), f"proposal {proposal_id}")


@step("Read which import created donor {donor_id}")
def read_donor_import_batch(db: DbQueries, donor_id: str) -> str | None:
    return db.donor_import_batch(donor_id)


@step("Count the records attributed to import batch {batch_id}")
def read_import_attribution(db: DbQueries, batch_id: str) -> dict[str, int]:
    return db.import_attribution(batch_id)


@step("Count the active donors and payments")
def read_active_catalog_counts(db: DbQueries) -> dict[str, int]:
    return db.active_catalog_counts()


@step("Read the canonical catalogue revision")
def read_catalog_revision(db: DbQueries) -> int:
    return db.catalog_revision()
