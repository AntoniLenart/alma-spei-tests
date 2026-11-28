"""Import response contracts.

Mirrors ``src/common/alma_spei/common/contracts/imports.cljc`` (task 35):
``batch`` (closed map + the ``counts-valid?`` and failed<->failure-code rules),
``row-payload``, ``staged-row``, ``rows-response`` and ``upload-response``.
Since task 67 the staged rows of a page depend on the batch's source: bank rows,
master workbook rows (profile fields and source observations, task 65's
``master-row``) or 1.5% tax rows (taxpayer, spouse, purpose, amount).
"""

from alma_spei_tests.contracts.donors import DONOR
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

# --- master and tax sources (tasks 65-67; contracts/source_rows.cljc) --------
OBSERVATION = ClosedMap(
    {
        "column": Int(7, 24),
        "source-type": Enum("text", "number", "boolean", "unsupported"),
        "value": SOURCE_TEXT,
    },
    optional={"year": Int(2021, 2025)},
)
MASTER_PAYLOAD = ClosedMap(
    {"observations": Vector(OBSERVATION)},
    optional={
        field: SOURCE_TEXT
        for field in ("name", "street", "postal-code", "city", "province", "gender")
    },
)
TAX_SUBJECT = AllOf(
    ClosedMap({}, optional={field: SOURCE_TEXT for field in ("first-name", "surname", "address")}),
    Predicate("a subject with at least one field", lambda v: isinstance(v, dict) and bool(v)),
)
TAX_PAYLOAD = ClosedMap(
    {"amount": Maybe(SOURCE_TEXT)},
    optional={"taxpayer": TAX_SUBJECT, "spouse": TAX_SUBJECT, "purpose": SOURCE_TEXT},
)


def _source_page(payload: ClosedMap, *, upload: bool) -> ClosedMap:
    row = ClosedMap({**STAGED_ROW.fields, "payload": payload})
    fields = {**_PAGE_FIELDS, "rows": Vector(row)}
    return ClosedMap({**fields, "skipped-empty-rows": ROW_COUNT} if upload else fields)


#: The rows and upload responses of each source (the response dispatches on it).
SOURCE_ROWS_RESPONSE = {
    "bank": ROWS_RESPONSE,
    "master": _source_page(MASTER_PAYLOAD, upload=False),
    "tax": _source_page(TAX_PAYLOAD, upload=False),
}
SOURCE_UPLOAD_RESPONSE = {
    "bank": UPLOAD_RESPONSE,
    "master": _source_page(MASTER_PAYLOAD, upload=True),
    "tax": _source_page(TAX_PAYLOAD, upload=True),
}


# --- review (task 37; contracts/review.cljc) ---------------------------------
BATCH_RESPONSE = ClosedMap({"batch": BATCH})
QUEUE_RESPONSE = ClosedMap(
    {"batches": Vector(BATCH), "total": ROW_COUNT, "limit": Int(1, 100), "offset": ROW_COUNT}
)
COMPARISON_RESPONSE = ClosedMap({"batch": BATCH, "row": STAGED_ROW, "donor": DONOR})
