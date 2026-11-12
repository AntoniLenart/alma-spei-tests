"""Python mirrors of the app's shared Malli contracts, for contract tests."""

from alma_spei_tests.contracts.auth import (
    ACCOUNT_RESPONSE,
    ACCOUNTS_RESPONSE,
    SESSION_RESPONSE,
    TEMPORARY_RESPONSE,
)
from alma_spei_tests.contracts.health import HEALTH_RESPONSE
from alma_spei_tests.contracts.schema import Schema

__all__ = [
    "ACCOUNTS_RESPONSE",
    "ACCOUNT_RESPONSE",
    "HEALTH_RESPONSE",
    "SESSION_RESPONSE",
    "Schema",
    "TEMPORARY_RESPONSE",
]
