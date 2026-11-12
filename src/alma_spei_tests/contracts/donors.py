"""Donor response contracts.

Mirrors ``src/common/alma_spei/common/contracts/donors.cljc`` (``donor``,
``donor-response``, ``donors-response``, ``donation``, ``detail-response``,
``audit-change``, ``audit-event``, ``history-response``).
"""

from alma_spei_tests.constants import EntityType
from alma_spei_tests.contracts.schema import (
    BOOLEAN,
    NONBLANK_STRING,
    SAFE_MAXIMUM,
    STRING,
    ClosedMap,
    Enum,
    Int,
    Maybe,
    Predicate,
    Regex,
    Vector,
)

IDENTIFIER = Regex(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
ENTITY_TYPE = Enum(*(t.value for t in EntityType))
VERSION = Int(1, SAFE_MAXIMUM)
TOTAL = Int(0, SAFE_MAXIMUM)

DONOR = ClosedMap(
    {
        "id": IDENTIFIER,
        "entity-type": ENTITY_TYPE,
        "name": NONBLANK_STRING,
        "first-name": Maybe(STRING),
        "street": Maybe(STRING),
        "postal-code": Maybe(STRING),
        "city": Maybe(STRING),
        "province": Maybe(STRING),
        "is-active": BOOLEAN,
        "version": VERSION,
    }
)

DONOR_RESPONSE = ClosedMap({"donor": DONOR})
DONORS_RESPONSE = ClosedMap({"donors": Vector(DONOR), "total": TOTAL})

DONATION = ClosedMap(
    {
        "id": IDENTIFIER,
        "amount": Regex(r"-?[0-9]{1,16}\.[0-9]{4}"),
        "currency": Regex(r"[A-Z]{3}"),
        "received-on": Regex(r"[0-9]{4}-[0-9]{2}-[0-9]{2}"),
    }
)

DETAIL_RESPONSE = ClosedMap(
    {"donor": DONOR, "donations": Vector(DONATION), "donations-total": TOTAL}
)

AUDIT_VALUE = Maybe(Predicate("a string or boolean", lambda v: isinstance(v, str | bool)))
AUDIT_CHANGE = ClosedMap(
    {
        "field": Enum(
            "entity-type",
            "name",
            "first-name",
            "street",
            "postal-code",
            "city",
            "province",
            "is-active",
        ),
        "before": AUDIT_VALUE,
        "after": AUDIT_VALUE,
    }
)
AUDIT_EVENT = ClosedMap(
    {
        "id": IDENTIFIER,
        "actor-id": IDENTIFIER,
        "actor-name": NONBLANK_STRING,
        "occurred-at": STRING,
        "action": Enum("create", "update", "archive", "merge"),
        "changes": Vector(AUDIT_CHANGE),
    }
)
HISTORY_RESPONSE = ClosedMap({"events": Vector(AUDIT_EVENT), "total": TOTAL})
