"""Automatic reconciliation contracts (tasks 60-62).

Mirrors ``src/common/alma_spei/common/contracts/reconciliation.cljc``: the
confirmed ``policy``, the ``counts``, and the report with the rows left for a
person (``exceptions``), their suggested donors with the reason for each, and
whether a row is a candidate for a new profile. Since task 62 the report is one
of two views (``queue``): the exceptions, or the automatic exact matches with
their donors.
"""

from alma_spei_tests.contracts.decisions import CURRENCY
from alma_spei_tests.contracts.donors import DONOR
from alma_spei_tests.contracts.imports import BATCH, POSITIVE, ROW_COUNT, STAGED_ROW
from alma_spei_tests.contracts.schema import (
    BOOLEAN,
    STRING,
    ClosedMap,
    Enum,
    Maybe,
    Vector,
)

POLICY = ClosedMap(
    {
        "currency": CURRENCY,
        "new-donor-type": Maybe(Enum("individual", "business", "organization")),
    }
)
COUNTS = ClosedMap(
    {
        "matched": ROW_COUNT,
        "new-donors": ROW_COUNT,
        "new-payments": ROW_COUNT,
        "duplicates": ROW_COUNT,
        "exceptions": ROW_COUNT,
        "total": ROW_COUNT,
    }
)
#: A suggested donor: its public profile and why it is suggested (task 61).
SUGGESTED_DONOR = ClosedMap({**DONOR.fields, "match-reason": STRING})
EXCEPTION_ROW = ClosedMap(
    {
        "row": STAGED_ROW,
        "reason": STRING,
        "new-profile-candidate": BOOLEAN,
        "candidates": Vector(SUGGESTED_DONOR),
    }
)
#: A row the matching linked to a donor automatically (task 62).
EXACT_MATCH = ClosedMap({"row": STAGED_ROW, "donor": DONOR})
RECONCILIATION_RESPONSE = ClosedMap(
    {
        "batch": BATCH,
        "catalog-version": POSITIVE,
        "policy": Maybe(POLICY),
        "counts": COUNTS,
        "totals": Vector(ClosedMap({"currency": CURRENCY, "amount": STRING})),
        "exceptions": Vector(EXCEPTION_ROW),
        "queue": Enum("exceptions", "exact"),
        "exact-match-count": ROW_COUNT,
        "exact-matches": Vector(EXACT_MATCH),
        "limit": POSITIVE,
        "offset": ROW_COUNT,
        "ready": BOOLEAN,
    }
)
