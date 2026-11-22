"""Python mirrors of the app's shared Malli contracts, for contract tests."""

from alma_spei_tests.contracts.auth import (
    ACCOUNT_RESPONSE,
    ACCOUNTS_RESPONSE,
    SESSION_RESPONSE,
    TEMPORARY_RESPONSE,
)
from alma_spei_tests.contracts.decisions import (
    BLOCKERS_RESPONSE,
    DECISION_RESPONSE,
    EVENTS_RESPONSE,
    ITEMS_RESPONSE,
    PAYMENTS_RESPONSE,
    PREVIEW_RESPONSE,
    PROPOSAL_RESPONSE,
    PROPOSALS_RESPONSE,
)
from alma_spei_tests.contracts.donors import (
    DETAIL_RESPONSE,
    DONOR,
    DONOR_RESPONSE,
    DONORS_RESPONSE,
    HISTORY_RESPONSE,
)
from alma_spei_tests.contracts.execution import (
    APPLIED_ITEMS_RESPONSE,
    BACKUP_RESPONSE,
    CAPABILITIES,
    ELIGIBILITY,
    IMPORT_HISTORY,
    OUTCOME,
)
from alma_spei_tests.contracts.health import HEALTH_RESPONSE
from alma_spei_tests.contracts.imports import (
    BATCH,
    BATCH_RESPONSE,
    COMPARISON_RESPONSE,
    QUEUE_RESPONSE,
    ROWS_RESPONSE,
    UPLOAD_RESPONSE,
)
from alma_spei_tests.contracts.reconciliation import RECONCILIATION_RESPONSE
from alma_spei_tests.contracts.schema import Schema

__all__ = [
    "APPLIED_ITEMS_RESPONSE",
    "BACKUP_RESPONSE",
    "CAPABILITIES",
    "ELIGIBILITY",
    "IMPORT_HISTORY",
    "OUTCOME",
    "ACCOUNTS_RESPONSE",
    "ACCOUNT_RESPONSE",
    "BATCH",
    "BATCH_RESPONSE",
    "BLOCKERS_RESPONSE",
    "COMPARISON_RESPONSE",
    "DECISION_RESPONSE",
    "DETAIL_RESPONSE",
    "DONOR",
    "DONORS_RESPONSE",
    "DONOR_RESPONSE",
    "EVENTS_RESPONSE",
    "HEALTH_RESPONSE",
    "HISTORY_RESPONSE",
    "ITEMS_RESPONSE",
    "PAYMENTS_RESPONSE",
    "PREVIEW_RESPONSE",
    "PROPOSALS_RESPONSE",
    "PROPOSAL_RESPONSE",
    "RECONCILIATION_RESPONSE",
    "QUEUE_RESPONSE",
    "ROWS_RESPONSE",
    "SESSION_RESPONSE",
    "Schema",
    "TEMPORARY_RESPONSE",
    "UPLOAD_RESPONSE",
]
