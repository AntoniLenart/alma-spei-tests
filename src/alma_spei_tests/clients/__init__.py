"""Encapsulated API clients composed by the ``AlmaSpeiApi`` facade."""

from alma_spei_tests.clients.accounts import AccountsClient
from alma_spei_tests.clients.auth import AuthClient
from alma_spei_tests.clients.base import ApiError, BaseClient, expect_status
from alma_spei_tests.clients.donors import DonorsClient
from alma_spei_tests.clients.facade import AlmaSpeiApi
from alma_spei_tests.clients.health import HealthClient

__all__ = [
    "AccountsClient",
    "AlmaSpeiApi",
    "ApiError",
    "AuthClient",
    "BaseClient",
    "DonorsClient",
    "HealthClient",
    "expect_status",
]
