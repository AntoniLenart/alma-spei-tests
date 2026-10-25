"""Shared constants and enums.

Literal values that tests or helpers would otherwise hard-code live here, so a
value is defined once and referenced by name everywhere.
"""

from enum import StrEnum


class ContentType(StrEnum):
    """MIME types the API uses."""

    JSON = "application/json"


class HealthStatus(StrEnum):
    """Allowed values of the health response ``status`` field."""

    OK = "ok"
    UNAVAILABLE = "unavailable"


#: The two allowed health status strings, as a tuple for membership checks.
HEALTH_STATUS_VALUES: tuple[str, ...] = tuple(status.value for status in HealthStatus)


class ApiErrorPayload:
    """Exact JSON error payloads the backend returns."""

    NOT_FOUND = {"code": "not-found", "message": "Nie znaleziono zasobu."}


#: Foundation migration (202610250001) seeds this version into application_metadata.
FOUNDATION_VERSION = 1

#: application_metadata is a singleton table (exactly one row).
SINGLETON_ROW_COUNT = 1
