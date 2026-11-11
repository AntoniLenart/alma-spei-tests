"""Encapsulated API clients composed by the ``AlmaSpeiApi`` facade."""

from alma_spei_tests.clients.auth import AuthClient
from alma_spei_tests.clients.base import ApiError, BaseClient, expect_status
from alma_spei_tests.clients.facade import AlmaSpeiApi

__all__ = ["AlmaSpeiApi", "ApiError", "AuthClient", "BaseClient", "expect_status"]
