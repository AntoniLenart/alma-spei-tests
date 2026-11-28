"""Shared constants and enums.

Literal values that tests or helpers would otherwise hard-code live here, so a
value is defined once and referenced by name everywhere. Polish strings are the
exact user-facing messages the backend returns; Polish UI strings live on the
page objects.
"""

from decimal import Decimal
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
    DONORS = "/api/donors"
    IMPORTS = "/api/imports"
    IMPORT_UPLOAD = "/api/imports/upload"
    IMPORT_REVIEW = "/api/imports/review"
    IMPORT_CAPABILITIES = "/api/imports/capabilities"
    IMPORT_COMMIT = "/api/imports/commit"
    IMPORT_UNDO_LAST = "/api/imports/undo-last"
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
    PASSWORD_CHANGE_REQUIRED = "password-change-required"
    FORBIDDEN = "forbidden"
    INVALID_CREDENTIALS = "invalid-credentials"
    THROTTLED = "throttled"
    VALIDATION = "validation"
    USERNAME_EXISTS = "username-exists"
    LAST_ADMINISTRATOR = "last-administrator"
    INVALID_PASSWORD = "invalid-password"
    PASSWORD_REUSED = "password-reused"
    STALE_DONOR = "stale-donor"
    MALFORMED_BODY = "malformed-body"
    BODY_TOO_LARGE = "body-too-large"
    # imports (the rejection codes double as batch failure codes)
    INVALID_STRUCTURE = "invalid-structure"
    UNSUPPORTED_FORMAT = "unsupported-format"
    PARSE_FAILED = "parse-failed"
    RESOURCE_LIMIT = "resource-limit"
    DUPLICATE_FILE = "duplicate-file"
    RETRY_FILE_MISMATCH = "retry-file-mismatch"
    INELIGIBLE_RETRY = "ineligible-retry"
    STALE_IMPORT = "stale-import"
    EMPTY_FILE = "empty-file"
    REVIEW_UNAVAILABLE = "review-unavailable"
    # review decisions and previews (task 38)
    STALE_REVIEW = "stale-review"
    INVALID_ROW = "invalid-row"
    INACTIVE_DONOR = "inactive-donor"
    DUPLICATE_MISMATCH = "duplicate-mismatch"
    REVIEW_BLOCKED = "review-blocked"
    # commit and undo (task 39)
    STALE_CATALOG = "stale-catalog"
    STALE_PREVIEW = "stale-preview"
    BACKUP_REQUIRED = "backup-required"
    DIFFERENT_REQUEST = "different-request"
    INELIGIBLE_UNDO = "ineligible-undo"
    UNDO_BLOCKED = "undo-blocked"
    # automatic reconciliation (task 60)
    POLICY_CONFLICT = "policy-conflict"


class ApiErrorPayload:
    """Exact JSON error payloads (``code`` + Polish ``message``) the backend returns."""

    NOT_FOUND = {"code": ErrorCode.NOT_FOUND, "message": "Nie znaleziono zasobu."}
    CSRF = {"code": ErrorCode.CSRF, "message": "Sesja formularza wygasła. Odśwież stronę."}
    UNAUTHENTICATED = {"code": ErrorCode.UNAUTHENTICATED, "message": "Zaloguj się ponownie."}
    PASSWORD_CHANGE_REQUIRED = {
        "code": ErrorCode.PASSWORD_CHANGE_REQUIRED,
        "message": "Najpierw zmień hasło tymczasowe.",
    }
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
    DONOR_NOT_FOUND = {"code": ErrorCode.NOT_FOUND, "message": "Nie znaleziono darczyńcy."}
    STALE_DONOR = {
        "code": ErrorCode.STALE_DONOR,
        "message": "Dane darczyńcy zostały zmienione. Odśwież formularz i sprawdź zmiany.",
    }
    MALFORMED_BODY = {
        "code": ErrorCode.MALFORMED_BODY,
        "message": "Nieprawidłowy format danych formularza.",
    }
    BODY_TOO_LARGE = {
        "code": ErrorCode.BODY_TOO_LARGE,
        "message": "Przekroczono rozmiar formularza.",
    }


class ImportErrorPayload:
    """``{code, message}`` of import rejections (bodies may add batch-id/batch)."""

    _BAD_FILE = "Nieprawidłowy format pliku importu."
    INVALID_STRUCTURE = {"code": ErrorCode.INVALID_STRUCTURE, "message": _BAD_FILE}
    PARSE_FAILED = {"code": ErrorCode.PARSE_FAILED, "message": _BAD_FILE}
    UNSUPPORTED_FORMAT = {"code": ErrorCode.UNSUPPORTED_FORMAT, "message": _BAD_FILE}
    RESOURCE_LIMIT = {
        "code": ErrorCode.RESOURCE_LIMIT,
        "message": "Plik przekracza limit importu.",
    }
    DUPLICATE_FILE = {
        "code": ErrorCode.DUPLICATE_FILE,
        "message": "Ten plik został już przesłany. Otwórz historię importów.",
    }
    RETRY_FILE_MISMATCH = {
        "code": ErrorCode.RETRY_FILE_MISMATCH,
        "message": "Ponowienie wymaga tego samego pliku źródłowego.",
    }
    INELIGIBLE_RETRY = {
        "code": ErrorCode.INELIGIBLE_RETRY,
        "message": "Można ponowić tylko ostatni nieudany lub wycofany import tego pliku.",
    }
    STALE_IMPORT = {
        "code": ErrorCode.STALE_IMPORT,
        "message": "Dane importu zostały zmienione. Odśwież widok.",
    }
    EMPTY_FILE = {"code": ErrorCode.EMPTY_FILE, "message": "Plik jest pusty."}
    NOT_FOUND = {"code": ErrorCode.NOT_FOUND, "message": "Nie znaleziono importu."}
    ROW_NOT_FOUND = {"code": ErrorCode.NOT_FOUND, "message": "Nie znaleziono wiersza importu."}
    REVIEW_UNAVAILABLE = {
        "code": ErrorCode.REVIEW_UNAVAILABLE,
        "message": "Ten import nie oczekuje na weryfikację. Odśwież kolejkę.",
    }
    VALIDATION = {"code": ErrorCode.VALIDATION, "message": "Sprawdź dane importu."}


class ReviewErrorPayload:
    """``{code, message}`` of review decision, proposal and preview errors (task 38)."""

    CSRF = {"code": ErrorCode.CSRF, "message": "Sesja formularza wygasła. Odśwież stronę."}
    QUERY = {"code": ErrorCode.VALIDATION, "message": "Nieprawidłowe parametry weryfikacji."}
    STALE_REVIEW = {
        "code": ErrorCode.STALE_REVIEW,
        "message": "Dane weryfikacji zmieniły się. Zachowaj potrzebne poprawki i odśwież widok.",
    }
    INVALID_ROW = {
        "code": ErrorCode.INVALID_ROW,
        "message": "Popraw wiersz w pliku źródłowym przed podjęciem decyzji.",
    }
    INACTIVE_DONOR = {
        "code": ErrorCode.INACTIVE_DONOR,
        "message": "Wybierz aktywny profil darczyńcy.",
    }
    REVIEW_UNAVAILABLE = {
        "code": ErrorCode.REVIEW_UNAVAILABLE,
        "message": "Ten import nie oczekuje na weryfikację.",
    }
    REVIEW_BLOCKED = {
        "code": ErrorCode.REVIEW_BLOCKED,
        "message": "Uzupełnij lub odśwież decyzje przed przygotowaniem podglądu.",
    }
    PROPOSAL_NOT_FOUND = {
        "code": ErrorCode.NOT_FOUND,
        "message": "Nie znaleziono propozycji darczyńcy.",
    }
    PREVIEW_NOT_FOUND = {"code": ErrorCode.NOT_FOUND, "message": "Nie znaleziono podglądu importu."}
    STALE_CATALOG = {
        "code": ErrorCode.STALE_CATALOG,
        "message": "Baza darczyńców lub wpłat zmieniła się. Wczytaj i zweryfikuj decyzje ponownie.",
    }


class ExecutionErrorPayload:
    """``{code, message}`` of backup, commit and undo refusals (task 39)."""

    STALE_PREVIEW = {
        "code": ErrorCode.STALE_PREVIEW,
        "message": (
            "Podgląd wymaga ponownej weryfikacji decyzji i przygotowania aktualnej wersji."
        ),
    }
    CHANGED_PREVIEW = {
        "code": ErrorCode.STALE_PREVIEW,
        "message": "Podgląd nie odpowiada potwierdzonym zmianom.",
    }
    BACKUP_REQUIRED = {
        "code": ErrorCode.BACKUP_REQUIRED,
        "message": "Wymagane jest aktualne potwierdzenie kopii zapasowej dla tego podglądu.",
    }
    DIFFERENT_REQUEST = {
        "code": ErrorCode.DIFFERENT_REQUEST,
        "message": "Operację już wykonano z innymi danymi. Otwórz aktualną historię importu.",
    }
    INELIGIBLE_UNDO = {
        "code": ErrorCode.INELIGIBLE_UNDO,
        "message": "Wskazany import nie ma oczekiwanego zatwierdzenia.",
    }
    UNDO_BLOCKED = {
        "code": ErrorCode.UNDO_BLOCKED,
        "message": "Wycofanie wstrzymano. Sprawdź aktualną listę powiązań i zmian.",
    }


class ReconciliationErrorPayload:
    """Refusals of the automatic reconciliation (task 60)."""

    POLICY_CONFLICT = {
        "code": ErrorCode.POLICY_CONFLICT,
        "message": (
            "Ten import ma już inne potwierdzone ustawienia. Nie zmieniono zapisanych decyzji."
        ),
    }


class ExceptionReason(StrEnum):
    """Why the reconciliation left a row for a person (``exceptions[].reason``)."""

    SENDER_FORMAT = "sender-format"
    IDENTITY_AMBIGUITY = "identity-ambiguity"
    DONOR_TYPE = "donor-type"
    PAYMENT_AMBIGUITY = "payment-ambiguity"
    INVALID_ROW = "invalid-row"
    UNSUPPORTED_AMOUNT = "unsupported-amount"
    STALE_CATALOG = "stale-catalog"
    MANUAL_REVIEW = "manual-review"


class MatchReason:
    """Why a donor is suggested for a row (``candidates[].match-reason``, task 61), from
    the strongest evidence to the weakest."""

    EXACT = "Zgodna pełna nazwa i pełny adres."
    NAME_AND_ADDRESS = "Podobna pełna nazwa i pełny adres."
    NAME = "Podobna pełna nazwa; adres różni się lub jest niepełny."
    ADDRESS = "Podobny pełny adres; nazwa się różni."
    LAST_NAME = "Zgodny ostatni człon nazwy; sprawdź imię i adres."


class ReconciliationQueue(StrEnum):
    """Views of the reconciliation report (``queue`` query parameter, task 62)."""

    EXCEPTIONS = "exceptions"
    EXACT = "exact"


#: At most this many donors are suggested for one row.
MAX_SUGGESTIONS = 5

#: The matching rules recorded on automatic decisions since task 60.
MATCHING_RULE_VERSION = "bank-exact-identity-v2"


class UndoConflict(StrEnum):
    """Why an import cannot be undone (``eligibility.blockers[].code``)."""

    NOT_LATEST = "not-latest"
    ALREADY_UNDONE = "already-undone"
    NOT_COMMITTED = "not-committed"
    CHANGED_DONOR = "changed-donor"
    CHANGED_PAYMENT = "changed-payment"
    DEPENDENT_RECORDS = "dependent-records"


#: The only backup provider implemented so far: labelled, synthetic, no real backup.
SYNTHETIC_BACKUP_ADAPTER = "synthetic-test-v1"

#: Its receipts are valid for five minutes (a development constant, not a policy).
SYNTHETIC_RECEIPT_LIFETIME_S = 300


class DecisionKind(StrEnum):
    """``kind`` of a saved row decision: which donor the row's payment belongs to."""

    UNRESOLVED = "unresolved"
    EXISTING_DONOR = "existing-donor"
    NEW_PROPOSAL = "new-proposal"


class Disposition(StrEnum):
    """``financial.disposition``: a separate new payment, or one already in the catalogue."""

    UNRESOLVED = "unresolved"
    NEW = "new"
    EXISTING = "existing"


class BlockerCode(StrEnum):
    """Readiness blocker ``code`` values of a review (contracts/decisions.cljc)."""

    INVALID_ROW = "invalid-row"
    MISSING_DECISION = "missing-decision"
    STALE_CATALOG = "stale-catalog"
    UNSUPPORTED_AMOUNT = "unsupported-amount"
    STALE_TARGET = "stale-target"
    INACTIVE_DONOR = "inactive-donor"
    DUPLICATE_MISMATCH = "duplicate-mismatch"


class PreviewItemKind(StrEnum):
    NEW_DONOR = "new-donor"
    EXISTING_DONOR_REFERENCE = "existing-donor-reference"
    NEW_PAYMENT = "new-payment"
    DUPLICATE_REFERENCE = "duplicate-reference"


class ReviewEventType(StrEnum):
    """``import_review_events.event_type`` values."""

    PROPOSAL_CREATED = "proposal-created"
    PROPOSAL_UPDATED = "proposal-updated"
    DECISION_SAVED = "decision-saved"
    DECISION_CLEARED = "decision-cleared"
    PREVIEW_CREATED = "preview-created"


#: A reviewer-asserted currency (three upper-case letters; there is no default).
REVIEW_CURRENCY = "PLN"
OTHER_CURRENCY = "EUR"

#: The longest evidence note a decision may carry.
EVIDENCE_MAX_LENGTH = 500

#: Rule version of previews built by task 38, and of the catalogue-bound ones since task 39.
PREVIEW_RULE_V1 = "review-preview-v1"
PREVIEW_RULE_V2 = "review-preview-v2"

#: Review pages (proposals, events, blockers, preview items) default to 25 entries.
REVIEW_PAGE_DEFAULT_LIMIT = 25


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


class DonorStatusFilter(StrEnum):
    """Values of the donor list ``status`` query parameter."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    ALL = "all"


class DonorSortField(StrEnum):
    """Columns the donor list can be sorted by."""

    NAME = "name"
    CITY = "city"
    ENTITY_TYPE = "entity-type"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class ImportSource(StrEnum):
    """Upload ``source`` values; only ``bank`` is implemented (task 35)."""

    BANK = "bank"
    TAX = "tax"


class CsvSeparator(StrEnum):
    SEMICOLON = ";"
    COMMA = ","


class ImportState(StrEnum):
    """``import_batches.state`` values reached so far."""

    RESERVED = "reserved"
    REVIEW = "review"
    FAILED = "failed"
    APPROVED = "approved"
    COMMITTED = "committed"
    UNDONE = "undone"


class ImportEvent(StrEnum):
    """``import_batch_events.event_type`` values reached so far."""

    RESERVED = "reserved"
    STAGED = "staged"
    FAILED = "failed"
    RETRY_REQUESTED = "retry-requested"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    COMMITTED = "committed"
    UNDONE = "undone"


class RowState(StrEnum):
    VALID = "valid"
    INVALID = "invalid"


class RowErrorCode(StrEnum):
    """Staged-row validation codes of the bank parser."""

    INVALID_DATE = "invalid-date"
    MISSING_SENDER = "missing-sender"
    INVALID_AMOUNT = "invalid-amount"


#: Polish message per staged-row validation code (contracts/imports.cljc ``row-messages``).
ROW_ERROR_MESSAGES: dict[str, str] = {
    RowErrorCode.INVALID_DATE: "Nieprawidłowa data transakcji.",
    RowErrorCode.MISSING_SENDER: "Brakuje danych nadawcy.",
    RowErrorCode.INVALID_AMOUNT: "Nieprawidłowa kwota transakcji.",
}

#: Parser/mapping versions recorded on staged bank batches.
BANK_PARSE_VERSION = "bank-parser-v1"
BANK_MAPPING_VERSION = "bank-four-columns-v1"

#: Upload limits (imports/limits.clj): file 5 MiB, whole request 6 MiB.
IMPORT_FILE_LIMIT_BYTES = 5 * 1024 * 1024

#: Staged-row pages default to 25 rows, at most 100.
IMPORT_PAGE_DEFAULT_LIMIT = 25
IMPORT_PAGE_MAX_LIMIT = 100

#: A freshly staged batch has gone reserved (1) -> review (2).
STAGED_BATCH_VERSION = 2


class AuditAction(StrEnum):
    """Donor audit event ``action`` values."""

    CREATE = "create"
    UPDATE = "update"
    ARCHIVE = "archive"


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


class SeedStatus(StrEnum):
    """``:status`` printed by the synthetic-data loader (``bb seed-demo``)."""

    LOADED = "loaded"
    UNCHANGED = "unchanged"


class DemoDataset:
    """The deterministic synthetic population (dev/alma_spei/dev/demo_data.clj)."""

    #: Every demo row's id is derived from this namespace (see ``data.demo``).
    ID_NAMESPACE = "alma-spei:synthetic-demo:v1"
    DONORS = 20
    PAYMENTS = 30
    ACTIVE = 18
    ARCHIVED = 2
    ENTITY_TYPES = {"individual": 12, "business": 4, "organization": 4}
    TOTAL = Decimal("2650.0000")
    CURRENCY = "PLN"
    YEAR = 2026
    #: Two separate profiles carry this full name, at different addresses.
    SHARED_NAME = "Jan Kowalski"
    #: Refusal when the chosen audit actor is not an active administrator.
    INVALID_ACTOR = (
        "Supply the username of an existing active account administrator;"
        " no accounts are created by this command."
    )


#: Donor list defaults applied by the backend when a query omits them.
DONOR_PAGE_DEFAULT_LIMIT = 25
DONOR_PAGE_MAX_LIMIT = 100

#: The first version a newly created donor gets; every effective update adds one.
INITIAL_DONOR_VERSION = 1

#: Non-GET request bodies are capped at 16 KiB by ``wrap-body-limit``.
BODY_LIMIT_BYTES = 16384

#: Logins are throttled at five attempts per username per 15 minutes.
LOGIN_ATTEMPTS_PER_USERNAME = 5

#: A session ends after 30 minutes without activity, and 8 hours after it began.
SESSION_IDLE_MINUTES = 30
SESSION_LIFETIME_HOURS = 8

#: Session tokens are 32 random bytes, base64url without padding (43 characters).
SESSION_TOKEN_LENGTH = 43


class BootstrapMessage(StrEnum):
    """Refusals of the first-administrator bootstrap (``bb create-admin``)."""

    #: The service refuses once any account exists.
    ALREADY_DONE = "Pierwsze konto zostało już utworzone."
    #: The console command's single, generic failure line.
    FAILED = (
        "Nie udało się utworzyć pierwszego administratora."
        " Sprawdź konfigurację, dane i istniejące konta."
    )


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
