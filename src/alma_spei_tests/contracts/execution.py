"""Import execution contracts (tasks 39-40): backup receipts, commit and undo outcomes.

Mirrors ``src/common/alma_spei/common/contracts/execution.cljc``: ``backup``,
``commit-receipt``, ``undo-receipt``, ``outcome``, ``history``, the undo
``eligibility`` with its ``conflict`` codes, and the applied ``items-response``.
Task 40 adds ``capabilities``, the history's ``uploaders`` and the outcome's
``uploaded-by-name`` (current display labels, never usernames).
"""

from alma_spei_tests.contracts.decisions import JSON_OBJECT, SHA256, SUMMARY
from alma_spei_tests.contracts.imports import BATCH, IDENTIFIER, POSITIVE, ROW_COUNT
from alma_spei_tests.contracts.schema import (
    BOOLEAN,
    STRING,
    ClosedMap,
    Const,
    Enum,
    Maybe,
    Vector,
)

_PAGE = {"total": ROW_COUNT, "limit": POSITIVE, "offset": ROW_COUNT}

BACKUP = ClosedMap(
    {
        "id": IDENTIFIER,
        "adapter": Const("synthetic-test-v1"),
        "synthetic": Const(True),
        "completed-at": STRING,
        "expires-at": STRING,
    }
)
BACKUP_RESPONSE = ClosedMap({"batch": BATCH, "backup": BACKUP})
COMMIT_RECEIPT = ClosedMap(
    {
        "id": IDENTIFIER,
        "ordinal": POSITIVE,
        "actor-id": IDENTIFIER,
        "actor-name": STRING,
        "occurred-at": STRING,
        "preview-id": IDENTIFIER,
        "effect-digest": SHA256,
        "batch-version": POSITIVE,
        "summary": SUMMARY,
        "backup": BACKUP,
    }
)
UNDO_RECEIPT = ClosedMap(
    {
        "id": IDENTIFIER,
        "actor-id": IDENTIFIER,
        "actor-name": STRING,
        "occurred-at": STRING,
        "batch-version": POSITIVE,
        "reversed-payments": ROW_COUNT,
        "archived-donors": ROW_COUNT,
    }
)
OUTCOME = ClosedMap(
    {
        "uploaded-by-name": STRING,
        "batch": BATCH,
        "commit": Maybe(COMMIT_RECEIPT),
        "undo": Maybe(UNDO_RECEIPT),
    }
)
UPLOADER = ClosedMap({"id": IDENTIFIER, "display-name": STRING})
IMPORT_HISTORY = ClosedMap({"uploaders": Vector(UPLOADER), "batches": Vector(BATCH), **_PAGE})
CAPABILITIES = ClosedMap({"commit-enabled": BOOLEAN, "mode": Enum("disabled", "synthetic-test-v1")})
CONFLICT = ClosedMap(
    {
        "code": Enum(
            "not-latest",
            "already-undone",
            "not-committed",
            "changed-donor",
            "changed-payment",
            "dependent-records",
        ),
        "entity-id": Maybe(IDENTIFIER),
    }
)
ELIGIBILITY = ClosedMap(
    {
        "batch": BATCH,
        "commit-id": Maybe(IDENTIFIER),
        "eligible": BOOLEAN,
        "blockers": Vector(CONFLICT),
        **_PAGE,
    }
)
APPLIED_ITEM = ClosedMap(
    {
        "ordinal": POSITIVE,
        "kind": STRING,
        "donor-id": IDENTIFIER,
        "donation-id": Maybe(IDENTIFIER),
        "proposal-id": Maybe(IDENTIFIER),
        "worksheet-index": Maybe(POSITIVE),
        "row-number": Maybe(POSITIVE),
        "donor-version": POSITIVE,
        "donation-version": Maybe(POSITIVE),
        "reversed": BOOLEAN,
        "snapshot": JSON_OBJECT,
    }
)
APPLIED_ITEMS_RESPONSE = ClosedMap({"batch": BATCH, "items": Vector(APPLIED_ITEM), **_PAGE})
