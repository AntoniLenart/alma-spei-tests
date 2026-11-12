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
    CONTENT_TYPE = "content-type"
    CACHE_CONTROL = "cache-control"
    CONTENT_TYPE_OPTIONS = "x-content-type-options"
    REFERRER_POLICY = "referrer-policy"


class SecurityHeaderValue(StrEnum):
    """Values of the security headers every response carries."""

    NO_STORE = "no-store"
    NOSNIFF = "nosniff"
    NO_REFERRER = "no-referrer"


class Cookie(StrEnum):
    """Cookie names the backend issues."""

    SESSION = "alma-session"
    CSRF = "alma-csrf"


class ApiPath(StrEnum):
    """Fixed API routes. Parameterised routes are built by the clients."""

    HEALTH_LIVE = "/api/health/live"
    HEALTH_READY = "/api/health/ready"
    AUTH_SESSION = "/api/auth/session"
    AUTH_LOGIN = "/api/auth/login"
    AUTH_LOGOUT = "/api/auth/logout"
    AUTH_PASSWORD = "/api/auth/password"
    ACCOUNTS = "/api/accounts"
    UNKNOWN = "/api/does-not-exist"


class HealthStatus(StrEnum):
    """Allowed values of the health response ``status`` field."""

    OK = "ok"
    UNAVAILABLE = "unavailable"


#: The two allowed health status strings, as a tuple for membership checks.
HEALTH_STATUS_VALUES: tuple[str, ...] = tuple(status.value for status in HealthStatus)


class ErrorCode(StrEnum):
    """Machine-readable ``code`` values of API error bodies."""

    NOT_FOUND = "not-found"
    CSRF = "csrf"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    INVALID_CREDENTIALS = "invalid-credentials"
    THROTTLED = "throttled"
    VALIDATION = "validation"
    USERNAME_EXISTS = "username-exists"
    LAST_ADMINISTRATOR = "last-administrator"
    INVALID_PASSWORD = "invalid-password"
    PASSWORD_REUSED = "password-reused"
    BODY_TOO_LARGE = "body-too-large"


class ApiErrorPayload:
    """Exact JSON error payloads (``code`` + Polish ``message``) the backend returns."""

    NOT_FOUND = {"code": ErrorCode.NOT_FOUND, "message": "Nie znaleziono zasobu."}
    CSRF = {"code": ErrorCode.CSRF, "message": "Sesja formularza wygasła. Odśwież stronę."}
    UNAUTHENTICATED = {"code": ErrorCode.UNAUTHENTICATED, "message": "Zaloguj się ponownie."}
    FORBIDDEN = {"code": ErrorCode.FORBIDDEN, "message": "Brak uprawnień do zarządzania kontami."}
    INVALID_CREDENTIALS = {
        "code": ErrorCode.INVALID_CREDENTIALS,
        "message": "Nieprawidłowa nazwa użytkownika lub hasło.",
    }
    THROTTLED = {
        "code": ErrorCode.THROTTLED,
        "message": "Zbyt wiele prób. Spróbuj ponownie za 15 minut.",
    }
    AUTH_VALIDATION = {
        "code": ErrorCode.VALIDATION,
        "message": "Sprawdź poprawność danych formularza.",
    }
    USERNAME_EXISTS = {
        "code": ErrorCode.USERNAME_EXISTS,
        "message": "Ta nazwa użytkownika jest już zajęta.",
    }
    LAST_ADMINISTRATOR = {
        "code": ErrorCode.LAST_ADMINISTRATOR,
        "message": "Nie można wyłączyć ostatniego aktywnego administratora.",
    }
    INVALID_PASSWORD = {
        "code": ErrorCode.INVALID_PASSWORD,
        "message": "Obecne hasło jest nieprawidłowe.",
    }
    PASSWORD_REUSED = {
        "code": ErrorCode.PASSWORD_REUSED,
        "message": "Nowe hasło musi być inne od obecnego.",
    }
    ACCOUNT_NOT_FOUND = {"code": ErrorCode.NOT_FOUND, "message": "Nie znaleziono konta."}
    BODY_TOO_LARGE = {
        "code": ErrorCode.BODY_TOO_LARGE,
        "message": "Przekroczono rozmiar formularza.",
    }


class FieldErrorCode(StrEnum):
    """Per-field ``errors[].code`` values of a donor validation response."""

    REQUIRED = "required"
    INVALID = "invalid"
    UNKNOWN_FIELD = "unknown-field"


class DonorFieldMessage(StrEnum):
    """Polish per-field validation messages (contracts/donors.cljc ``field-messages``)."""

    NAME = "Podaj nazwę lub imię i nazwisko darczyńcy."
    CITY = "Podaj miejscowość."
    POSTAL_CODE = "Podaj kod pocztowy w formacie XX-XXX."
    UNKNOWN_FIELD = "Formularz zawiera nieobsługiwane pole."


class EntityType(StrEnum):
    """Donor ``entity-type`` values."""

    INDIVIDUAL = "individual"
    BUSINESS = "business"
    ORGANIZATION = "organization"


class SecurityEvent(StrEnum):
    """``security_audit_events.event_type`` values written by the auth service."""

    BOOTSTRAP = "bootstrap"
    LOGIN = "login"
    LOGIN_FAILED = "login-failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password-changed"
    ACCOUNT_CREATED = "account-created"
    ACCOUNT_UPDATED = "account-updated"
    PASSWORD_RESET = "password-reset"


class Privilege(StrEnum):
    """PostgreSQL privileges checked on the app role (``has_table_privilege``)."""

    SELECT = "SELECT"
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    TRUNCATE = "TRUNCATE"


#: Non-GET request bodies are capped at 16 KiB by ``wrap-body-limit``.
BODY_LIMIT_BYTES = 16384

#: Logins are throttled at five attempts per username per 15 minutes.
LOGIN_ATTEMPTS_PER_USERNAME = 5

#: A temporary password issued by bootstrap/create/reset is at least this long.
TEMPORARY_PASSWORD_MIN_LENGTH = 20

#: Foundation migration (202610250001) seeds this version into application_metadata.
FOUNDATION_VERSION = 1

#: application_metadata is a singleton table (exactly one row).
SINGLETON_ROW_COUNT = 1

#: A password that satisfies the policy (8-128 chars, upper, digit, symbol, no
#: spaces). Accounts created by tests are rotated to it; it is synthetic.
KNOWN_PASSWORD = "QaAdmin!2026xyz"

#: A second policy-valid password, for rotating away from KNOWN_PASSWORD.
ROTATED_PASSWORD = "QaRotated#2026abc"

#: Violates the policy (no uppercase, no symbol) - rejected with 422.
WEAK_PASSWORD = "weakpassword1"

#: Policy-valid but wrong for every account - used for failed-login checks.
WRONG_PASSWORD = "Wrong-Password9!"
