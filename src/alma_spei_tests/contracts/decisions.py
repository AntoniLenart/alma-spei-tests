"""Review decision, donor proposal and preview contracts (task 38).

Mirrors ``src/common/alma_spei/common/contracts/decisions.cljc``: ``proposal``,
``decision``, the proposal/decision/blocker/payment/event responses, and the
immutable ``preview`` with its paged ``items``.
"""

from alma_spei_tests.contracts.donors import ENTITY_TYPE
from alma_spei_tests.contracts.imports import BATCH, IDENTIFIER, POSITIVE, ROW_COUNT, STAGED_ROW
from alma_spei_tests.contracts.schema import (
    BOOLEAN,
    NONBLANK_STRING,
    STRING,
    ClosedMap,
    Enum,
    Int,
    Maybe,
    Predicate,
    Regex,
    Vector,
)

SHA256 = Regex(r"[0-9a-f]{64}")
CURRENCY = Regex(r"[A-Z]{3}")
EXPECTED_VERSION = Int(0)
JSON_OBJECT = Predicate("a JSON object", lambda v: isinstance(v, dict))

PROFILE = ClosedMap(
    {
        "entity-type": ENTITY_TYPE,
        "name": NONBLANK_STRING,
        "city": NONBLANK_STRING,
        "first-name": Maybe(STRING),
        "street": Maybe(STRING),
        "postal-code": Maybe(STRING),
        "province": Maybe(STRING),
    }
)
FINANCIAL = ClosedMap(
    {
        "currency": Maybe(CURRENCY),
        "evidence": Predicate(
            "a string of at most 500 chars", lambda v: isinstance(v, str) and len(v) <= 500
        ),
        "disposition": Enum("unresolved", "new", "existing"),
        "overlap-checked": BOOLEAN,
    }
)
DECISION_FIELDS = {
    "kind": Enum("unresolved", "existing-donor", "new-proposal"),
    "donor-id": Maybe(IDENTIFIER),
    "proposal-id": Maybe(IDENTIFIER),
    "target-version": Maybe(POSITIVE),
    "financial": Maybe(FINANCIAL),
    "donation-id": Maybe(IDENTIFIER),
    "donation-version": Maybe(POSITIVE),
}
DECISION = ClosedMap(
    {
        "version": POSITIVE,
        "reviewer-id": IDENTIFIER,
        "reviewer-name": Maybe(STRING),
        "target-label": Maybe(STRING),
        "reviewed-at": STRING,
        "complete": BOOLEAN,
        **DECISION_FIELDS,
    }
)
PROPOSAL = ClosedMap(
    {
        "id": IDENTIFIER,
        "batch-id": IDENTIFIER,
        "version": POSITIVE,
        "profile": PROFILE,
        "created-by": IDENTIFIER,
        "updated-by": IDENTIFIER,
        "created-at": STRING,
        "updated-at": STRING,
    }
)
_PAGE = {"total": ROW_COUNT, "limit": POSITIVE, "offset": ROW_COUNT}

PROPOSAL_RESPONSE = ClosedMap({"batch": BATCH, "proposal": PROPOSAL})
PROPOSALS_RESPONSE = ClosedMap({"batch": BATCH, "proposals": Vector(PROPOSAL), **_PAGE})
DECISION_RESPONSE = ClosedMap({"batch": BATCH, "row": STAGED_ROW, "decision": Maybe(DECISION)})
BLOCKER = ClosedMap({"worksheet-index": POSITIVE, "row-number": POSITIVE, "code": STRING})
BLOCKERS_RESPONSE = ClosedMap({"batch": BATCH, "blockers": Vector(BLOCKER), **_PAGE})
PAYMENT = ClosedMap(
    {
        "id": IDENTIFIER,
        "version": POSITIVE,
        "amount": STRING,
        "currency": CURRENCY,
        "received-on": STRING,
    }
)
PAYMENTS_RESPONSE = ClosedMap(
    {"batch": BATCH, "donor-id": IDENTIFIER, "payments": Vector(PAYMENT), **_PAGE}
)
ITEM = ClosedMap(
    {
        "ordinal": POSITIVE,
        "kind": Enum("new-donor", "existing-donor-reference", "new-payment", "duplicate-reference"),
        "target-id": Maybe(IDENTIFIER),
        "worksheet-index": Maybe(POSITIVE),
        "row-number": Maybe(POSITIVE),
        "payload": JSON_OBJECT,
    }
)
SUMMARY = ClosedMap(
    {
        "new-donors": ROW_COUNT,
        "new-payments": ROW_COUNT,
        "duplicate-references": ROW_COUNT,
        "totals": Vector(ClosedMap({"currency": CURRENCY, "amount": STRING})),
    }
)
PREVIEW = ClosedMap(
    {
        "id": IDENTIFIER,
        "batch-id": IDENTIFIER,
        "batch-version": POSITIVE,
        "created-by": IDENTIFIER,
        "created-at": STRING,
        "rule-version": Enum("review-preview-v1"),
        "effect-digest": SHA256,
        "item-count": ROW_COUNT,
        "summary": SUMMARY,
    }
)
PREVIEW_RESPONSE = ClosedMap({"batch": BATCH, "preview": PREVIEW, "stale": BOOLEAN})
ITEMS_RESPONSE = ClosedMap({"preview": PREVIEW, "items": Vector(ITEM), **_PAGE})
REVIEW_EVENT = ClosedMap(
    {
        "id": IDENTIFIER,
        "actor-id": IDENTIFIER,
        "actor-name": STRING,
        "occurred-at": STRING,
        "event-type": Enum(
            "proposal-created",
            "proposal-updated",
            "decision-saved",
            "decision-cleared",
            "preview-created",
        ),
        "proposal-id": Maybe(IDENTIFIER),
        "preview-id": Maybe(IDENTIFIER),
        "worksheet-index": Maybe(POSITIVE),
        "row-number": Maybe(POSITIVE),
        "before-version": EXPECTED_VERSION,
        "after-version": POSITIVE,
        "before": Maybe(JSON_OBJECT),
        "after": JSON_OBJECT,
    }
)
EVENTS_RESPONSE = ClosedMap({"batch": BATCH, "events": Vector(REVIEW_EVENT), **_PAGE})
