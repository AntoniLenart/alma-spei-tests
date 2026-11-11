"""HTTP transport: the cookie + CSRF aware session the API clients share."""

from alma_spei_tests.http.session import AuthSession, HeaderOverrides

__all__ = ["AuthSession", "HeaderOverrides"]
