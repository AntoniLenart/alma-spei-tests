"""Review decisions for staged bank rows (task 38).

A decision says which donor a row's payment belongs to (an existing active
donor, a donor proposal of the same batch, or unresolved) and how the payment
is treated: a reviewer-asserted currency, a short evidence note, a new payment
or one already in the catalogue, and an explicit overlap check. Nothing is
inferred - every field is the reviewer's explicit choice.

``to_payload`` adds the optimistic versions the backend requires: the batch
version, the row's current decision version (0 before the first save) and, when
the server reports one, the catalogue revision the reviewer worked against.
"""

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from alma_spei_tests.constants import REVIEW_CURRENCY, DecisionKind, Disposition


@dataclass(frozen=True)
class Financial:
    currency: str | None = REVIEW_CURRENCY
    evidence: str = "Waluta potwierdzona w syntetycznym wyciągu testowym."
    disposition: Disposition = Disposition.NEW
    overlap_checked: bool = True

    def to_payload(self) -> dict[str, object]:
        return {
            "currency": self.currency,
            "evidence": self.evidence,
            "disposition": self.disposition.value,
            "overlap-checked": self.overlap_checked,
        }

    def with_changes(self, **changes: Any) -> "Financial":
        return dataclasses.replace(self, **changes)


#: Identity chosen, payment treatment still open: saved, but not complete.
UNDECIDED_PAYMENT = Financial(
    currency=None, evidence="", disposition=Disposition.UNRESOLVED, overlap_checked=False
)


@dataclass(frozen=True)
class ReviewVersions:
    """What the server reported for a row before a write."""

    batch_version: int
    decision_version: int
    catalog_version: int | None = None


@dataclass(frozen=True)
class RowDecision:
    kind: DecisionKind
    donor_id: str | None = None
    proposal_id: str | None = None
    target_version: int | None = None
    financial: Financial | None = None
    donation_id: str | None = None
    donation_version: int | None = None

    def to_payload(self, versions: ReviewVersions) -> dict[str, object]:
        payload: dict[str, object] = {
            "batch-version": versions.batch_version,
            "version": versions.decision_version,
            "kind": self.kind.value,
            "donor-id": self.donor_id,
            "proposal-id": self.proposal_id,
            "target-version": self.target_version,
            "financial": self.financial.to_payload() if self.financial else None,
            "donation-id": self.donation_id,
            "donation-version": self.donation_version,
        }
        if versions.catalog_version is not None:
            payload["catalog-version"] = versions.catalog_version
        return payload

    def with_changes(self, **changes: Any) -> "RowDecision":
        return dataclasses.replace(self, **changes)


def existing_donor(donor: dict[str, Any], financial: Financial | None = None) -> RowDecision:
    """Link the row to an existing donor (as returned by the API) as a new payment."""
    return RowDecision(
        kind=DecisionKind.EXISTING_DONOR,
        donor_id=donor["id"],
        target_version=donor["version"],
        financial=financial or Financial(),
    )


def proposed_donor(proposal: dict[str, Any], financial: Financial | None = None) -> RowDecision:
    """Link the row to a donor proposal of the same batch as a new payment."""
    return RowDecision(
        kind=DecisionKind.NEW_PROPOSAL,
        proposal_id=proposal["id"],
        target_version=proposal["version"],
        financial=financial or Financial(),
    )


def already_recorded(
    donor: dict[str, Any], payment: dict[str, Any], financial: Financial | None = None
) -> RowDecision:
    """The row is a payment already in the catalogue (an explicit duplicate reference)."""
    base = financial or Financial(currency=payment["currency"])
    return RowDecision(
        kind=DecisionKind.EXISTING_DONOR,
        donor_id=donor["id"],
        target_version=donor["version"],
        financial=base.with_changes(disposition=Disposition.EXISTING),
        donation_id=payment["id"],
        donation_version=payment["version"],
    )


UNRESOLVED = RowDecision(kind=DecisionKind.UNRESOLVED)


def proposal_payload(
    profile: Mapping[str, object], batch_version: int, catalog_version: int | None = None
) -> dict[str, object]:
    """POST body for a new donor proposal: the profile plus both explicit checks."""
    payload: dict[str, object] = {
        "batch-version": batch_version,
        "profile": profile,
        "checked-existing": True,
        "checked-proposals": True,
    }
    if catalog_version is not None:
        payload["catalog-version"] = catalog_version
    return payload
