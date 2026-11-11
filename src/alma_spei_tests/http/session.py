"""One browser-like HTTP session against the Alma Spei backend.

The backend authenticates with two HttpOnly cookies:

* ``alma-session`` - the session token, issued on login / password change;
* ``alma-csrf``    - a signed CSRF token, (re)issued on every auth response.

Every mutation (non-GET) must carry the ``alma-csrf`` cookie, an
``X-CSRF-Token`` header equal to it, and an ``Origin`` header equal to the app
origin. The session also stores a digest of the CSRF token it was issued with,
so the same cookie must be kept across login and later calls - which a single
cookie jar does naturally.

``AuthSession`` owns exactly that state and nothing else: the httpx client, its
cookie jar, the origin, and the CSRF headers. Endpoint knowledge lives in the
sub-clients (``alma_spei_tests.clients``); multi-step workflows live on the
``AlmaSpeiApi`` facade.
"""

from collections.abc import Mapping
from types import TracebackType
from typing import Any

import httpx

from alma_spei_tests.constants import ContentType, Cookie, Header

#: Methods the backend treats as non-mutating (no CSRF/Origin check).
SAFE_METHODS = frozenset({"GET", "HEAD"})

#: Header overrides: a ``None`` value removes a header the session would send.
HeaderOverrides = Mapping[str, str | None]


class AuthSession:
    def __init__(self, base_url: str, *, timeout: float):
        self.origin = base_url.rstrip("/")
        self._http = httpx.Client(
            base_url=self.origin,
            timeout=timeout,
            headers={"Accept": ContentType.JSON},
        )

    # --- lifecycle ------------------------------------------------------------
    def __enter__(self) -> "AuthSession":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ):
        self.close()

    def close(self):
        self._http.close()

    # --- state ----------------------------------------------------------------
    @property
    def csrf_token(self) -> str | None:
        """The current ``alma-csrf`` cookie value, if one has been issued."""
        return self._http.cookies.get(Cookie.CSRF)

    @property
    def session_token(self) -> str | None:
        """The current ``alma-session`` cookie value, if logged in."""
        return self._http.cookies.get(Cookie.SESSION)

    def cookies(self) -> dict[str, str]:
        """The auth cookies currently held, e.g. to hand to a browser context."""
        held = {Cookie.SESSION: self.session_token, Cookie.CSRF: self.csrf_token}
        return {str(name): value for name, value in held.items() if value is not None}

    # --- transport ------------------------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        *,
        headers: HeaderOverrides | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a request; mutations get Origin + X-CSRF-Token automatically.

        ``headers`` overrides the defaults; a ``None`` value drops that header
        (used by negative CSRF tests). The response is returned as-is - callers
        inspect the status code, the session never raises on non-2xx.
        """
        merged: dict[str, str | None] = {}
        if method.upper() not in SAFE_METHODS:
            merged = {Header.ORIGIN: self.origin, Header.CSRF_TOKEN: self.csrf_token}
        merged.update(headers or {})
        sent = {name: value for name, value in merged.items() if value is not None}
        return self._http.request(method, path, headers=sent, **kwargs)

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("PATCH", path, **kwargs)
