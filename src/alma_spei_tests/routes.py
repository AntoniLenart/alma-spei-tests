"""The backend's API routes, for the security sweeps.

Mirrors the reitit route tables in ``src/api/alma_spei/api/http/*.clj``. The
security tests send every route a request without a session, with a temporary
password, as a non-administrator, or without a valid CSRF token and origin. Path
parameters are filled with ids that exist nowhere, so a request that wrongly got
through would still change nothing.
"""

import uuid
from dataclasses import dataclass
from typing import Any

#: Path parameters of the route templates.
PLACEHOLDERS = ("{id}", "{preview}", "{proposal}")
ROW_PLACEHOLDERS = ("{worksheet}", "{row}")


@dataclass(frozen=True)
class Route:
    method: str
    path: str
    #: Reachable without a session (health, the session probe, login, logout).
    public: bool = False
    #: Account management: administrators only.
    admin_only: bool = False
    #: Still allowed while the account has a temporary password.
    temporary_password_allowed: bool = False
    #: The upload takes a multipart form instead of JSON.
    multipart: bool = False

    @property
    def mutating(self) -> bool:
        return self.method != "GET"

    @property
    def id(self) -> str:
        return f"{self.method} {self.path}"

    def url(self) -> str:
        path = self.path
        for placeholder in PLACEHOLDERS:
            path = path.replace(placeholder, str(uuid.uuid4()))
        for placeholder in ROW_PLACEHOLDERS:
            path = path.replace(placeholder, "1")
        return path

    def body(self) -> dict[str, Any]:
        """Request keyword arguments: an empty JSON object, or a tiny multipart upload."""
        if self.multipart:
            return {
                "files": {"file": ("qa-probe.csv", b"2026-01-15;QA;probe;1,00\n", "text/csv")},
                "data": {"source": "bank", "separator": ";"},
            }
        return {"json": {}} if self.mutating else {}


ROUTES = (
    Route("GET", "/api/health/live", public=True),
    Route("GET", "/api/health/ready", public=True),
    Route("GET", "/api/auth/session", public=True, temporary_password_allowed=True),
    Route("POST", "/api/auth/login", public=True, temporary_password_allowed=True),
    Route("POST", "/api/auth/logout", public=True, temporary_password_allowed=True),
    Route("POST", "/api/auth/password", temporary_password_allowed=True),
    Route("GET", "/api/accounts", admin_only=True),
    Route("POST", "/api/accounts", admin_only=True),
    Route("PATCH", "/api/accounts/{id}", admin_only=True),
    Route("POST", "/api/accounts/{id}/reset-password", admin_only=True),
    Route("GET", "/api/donors"),
    Route("POST", "/api/donors"),
    Route("GET", "/api/donors/{id}"),
    Route("PUT", "/api/donors/{id}"),
    Route("GET", "/api/donors/{id}/history"),
    Route("GET", "/api/imports/capabilities"),
    Route("GET", "/api/imports"),
    Route("POST", "/api/imports/commit"),
    Route("POST", "/api/imports/undo-last"),
    Route("POST", "/api/imports/{id}/previews/{preview}/backup"),
    Route("GET", "/api/imports/{id}/outcome"),
    Route("GET", "/api/imports/{id}/commit-items"),
    Route("GET", "/api/imports/{id}/undo-eligibility"),
    Route("GET", "/api/imports/review"),
    Route("POST", "/api/imports/upload", multipart=True),
    Route("GET", "/api/imports/{id}"),
    Route("GET", "/api/imports/{id}/rows/{worksheet}/{row}/comparison"),
    Route("GET", "/api/imports/{id}/rows"),
    Route("POST", "/api/imports/{id}/reconciliation/identity"),
    Route("GET", "/api/imports/{id}/reconciliation"),
    Route("POST", "/api/imports/{id}/reconciliation"),
    Route("GET", "/api/imports/{id}/donor-proposals"),
    Route("POST", "/api/imports/{id}/donor-proposals"),
    Route("PUT", "/api/imports/{id}/donor-proposals/{proposal}"),
    Route("GET", "/api/imports/{id}/rows/{worksheet}/{row}/decision"),
    Route("PUT", "/api/imports/{id}/rows/{worksheet}/{row}/decision"),
    Route("GET", "/api/imports/{id}/payments"),
    Route("GET", "/api/imports/{id}/review-events"),
    Route("GET", "/api/imports/{id}/review-blockers"),
    Route("POST", "/api/imports/{id}/preview"),
    Route("GET", "/api/imports/{id}/previews/{preview}"),
    Route("GET", "/api/imports/{id}/previews/{preview}/items"),
)

PROTECTED = tuple(route for route in ROUTES if not route.public)
MUTATIONS = tuple(route for route in ROUTES if route.mutating)
ADMIN_ONLY = tuple(route for route in ROUTES if route.admin_only)
BLOCKED_BY_TEMPORARY_PASSWORD = tuple(
    route for route in PROTECTED if not route.temporary_password_allowed
)
