"""Shared constants and enums.

Literal values that tests or helpers would otherwise hard-code live here, so a
value is defined once and referenced by name everywhere. Polish strings are the
exact user-facing messages the backend returns; Polish UI strings live on the
page objects.
"""

from enum import StrEnum


class ContentType(StrEnum):
    """MIME types the API uses."""

    JSON = "application/json"


class Header(StrEnum):
    """HTTP header names the client sets or the tests inspect."""

    ORIGIN = "Origin"
    CSRF_TOKEN = "X-CSRF-Token"


class Cookie(StrEnum):
    """Cookie names the backend issues."""

    SESSION = "alma-session"
    CSRF = "alma-csrf"


class ApiPath(StrEnum):
    """Fixed API routes. Parameterised routes are built by the clients."""

    AUTH_SESSION = "/api/auth/session"
    AUTH_LOGIN = "/api/auth/login"
    AUTH_PASSWORD = "/api/auth/password"


#: A temporary password issued by bootstrap/create/reset is at least this long.
TEMPORARY_PASSWORD_MIN_LENGTH = 20


#: A password that satisfies the policy (8-128 chars, upper, digit, symbol, no
#: spaces). Accounts created by tests are rotated to it; it is synthetic.
KNOWN_PASSWORD = "QaAdmin!2026xyz"
