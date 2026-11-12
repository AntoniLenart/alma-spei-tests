"""Import response contracts.

Mirrors ``src/common/alma_spei/common/contracts/imports.cljc`` (task 35):
``batch`` (closed map + the ``counts-valid?`` and failed<->failure-code rules),
``row-payload``, ``staged-row``, ``rows-response`` and ``upload-response``.
"""

from alma_spei_tests.contracts.schema import (
    SAFE_MAXIMUM,
    STRING,
    AllOf,
    ClosedMap,
    Const,
    Enum,
    Int,
    Maybe,
    Predicate,
    Regex,
    Vector,
)

IDENTIFIER = Regex(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
POSITIVE = Int(1, SAFE_MAXIMUM)
ROW_COUNT = Int(0, SAFE_MAXIMUM)
SOURCE = Enum("master", "tax", "bank")
STATE = Enum(
    "reserved", "staging", "review", "approved", "committed", "failed", "cancelled", "undone"
)
FAILURE_CODE = Enum(
    "parse-failed",
    "unsupported-format",
    "invalid-structure",
    "resource-limit",
    "processing-interrupted",
)
FILENAME = Predicate(
    "a bare file name",
    lambda v: (
        isinstance(v, str)
        and 1 <= len(v) <= 255
        and bool(v.strip())
        and v not in {".", ".."}
        and not any(ch in v for ch in "/\\")
        and not any(ord(ch) < 0x20 or 0x7F <= ord(ch) <= 0x9F for ch in v)
    ),
)

_COUNTS = ("total-rows", "valid-rows", "invalid-rows", "reviewed-rows")


def _counts_valid(batch: object) -> bool:
    """Port of ``counts-valid?``: consistent row counts for the batch state."""
    if not isinstance(batch, dict):
        return False
    counts = [batch.get(key) for key in _COUNTS]
    unknown = all(c is None for c in counts)
    ints = [c for c in counts if isinstance(c, int) and not isinstance(c, bool)]
    known = len(ints) == len(_COUNTS)
    consistent = settled = False
    if known:
        total, valid, invalid, reviewed = ints
        consistent = total == valid + invalid and reviewed <= valid
        settled = invalid == 0 and valid == reviewed
    state = batch.get("state")
    return (
        (unknown or consistent)
        and (state not in {"review", "approved", "committed", "undone"} or known)
        and (state not in {"approved", "committed", "undone"} or settled)
    )


BATCH = AllOf(
    ClosedMap(
        {
            "id": IDENTIFIER,
            "file-id": IDENTIFIER,
            "attempt-number": POSITIVE,
            "retry-of": Maybe(IDENTIFIER),
            "source-type": SOURCE,
            "original-filename": FILENAME,
            "byte-count": POSITIVE,
            "created-by": IDENTIFIER,
            "created-at": STRING,
            "updated-at": STRING,
            "version": POSITIVE,
            "state": STATE,
            "failure-code": Maybe(FAILURE_CODE),
            "parse-version": Maybe(STRING),
            "mapping-version": Maybe(STRING),
            "total-rows": Maybe(ROW_COUNT),
            "valid-rows": Maybe(ROW_COUNT),
            "invalid-rows": Maybe(ROW_COUNT),
            "reviewed-rows": Maybe(ROW_COUNT),
        }
    ),
    Predicate("row counts consistent with the state (counts-valid?)", _counts_valid),
    Predicate(
        "failure-code present exactly when the state is failed",
        lambda b: (
            isinstance(b, dict)
            and (b.get("state") == "failed") == (b.get("failure-code") is not None)
        ),
    ),
)

SOURCE_TEXT = Predicate(
    "a string of at most 4096 chars", lambda v: isinstance(v, str) and len(v) <= 4096
)
ROW_PAYLOAD = ClosedMap(
    {
        "date": Maybe(STRING),
        "sender": SOURCE_TEXT,
        "description": SOURCE_TEXT,
        "amount": Maybe(STRING),
        "currency": Const(None),
        "source-date": SOURCE_TEXT,
        "source-amount": SOURCE_TEXT,
    }
)
STAGED_ROW = ClosedMap(
    {
        "worksheet-index": POSITIVE,
        "row-number": POSITIVE,
        "payload": ROW_PAYLOAD,
        "validation-state": Enum("valid", "invalid"),
        "errors": Vector(ClosedMap({"code": STRING, "message": STRING})),
    }
)
_PAGE_FIELDS = {
    "batch": BATCH,
    "rows": Vector(STAGED_ROW),
    "total": ROW_COUNT,
    "limit": POSITIVE,
    "offset": ROW_COUNT,
}
ROWS_RESPONSE = ClosedMap(_PAGE_FIELDS)
UPLOAD_RESPONSE = ClosedMap({**_PAGE_FIELDS, "skipped-empty-rows": ROW_COUNT})
