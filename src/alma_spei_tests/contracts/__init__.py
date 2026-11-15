"""Python mirrors of the app's shared Malli contracts, for contract tests."""

from alma_spei_tests.contracts.auth import (
    ACCOUNT_RESPONSE,
    ACCOUNTS_RESPONSE,
    SESSION_RESPONSE,
    TEMPORARY_RESPONSE,
)
from alma_spei_tests.contracts.donors import (
    DETAIL_RESPONSE,
    DONOR,
    DONOR_RESPONSE,
    DONORS_RESPONSE,
    HISTORY_RESPONSE,
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
from alma_spei_tests.contracts.schema import Schema

__all__ = [
    "ACCOUNTS_RESPONSE",
    "ACCOUNT_RESPONSE",
    "BATCH",
    "BATCH_RESPONSE",
    "COMPARISON_RESPONSE",
    "DETAIL_RESPONSE",
    "DONOR",
    "DONORS_RESPONSE",
    "DONOR_RESPONSE",
    "HEALTH_RESPONSE",
    "HISTORY_RESPONSE",
    "QUEUE_RESPONSE",
    "ROWS_RESPONSE",
    "SESSION_RESPONSE",
    "Schema",
    "TEMPORARY_RESPONSE",
    "UPLOAD_RESPONSE",
]
