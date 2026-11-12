"""Reusable steps for direct database checks."""

from collections.abc import Sequence
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
