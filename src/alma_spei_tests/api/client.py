"""Thin httpx wrapper for the Alma Spei HTTP API.

Keeps a single configured client (base URL, timeout) and exposes small helpers
so tests and steps never construct URLs or parse JSON by hand. The client does
not raise on non-2xx by default: API tests routinely assert on 404/503, so the
caller inspects ``response.status_code`` explicitly.
"""

from types import TracebackType

import httpx


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    # context-manager support
    def __enter__(self) -> "ApiClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ):
        self.close()

    def close(self):
        self._client.close()

    # requests
    def get(self, path: str, **kwargs) -> httpx.Response:
        return self._client.get(path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self._client.post(path, **kwargs)

    # convenience
    def get_json(self, path: str, **kwargs) -> dict:
        return self.get(path, **kwargs).json()
