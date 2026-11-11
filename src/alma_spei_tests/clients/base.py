"""Shared base for the endpoint clients."""

from http import HTTPStatus

import httpx

from alma_spei_tests.http import AuthSession


class ApiError(RuntimeError):
    """A setup/workflow call got an unexpected response.

    Tests assert on responses themselves; this is only raised by workflows and
    setup steps that need a call to succeed before the scenario can continue.
    """

    def __init__(self, action: str, response: httpx.Response):
        super().__init__(
            f"{action} failed: HTTP {response.status_code} {response.request.method} "
            f"{response.request.url.path} -> {response.text[:500]}"
        )
        self.response = response


def expect_status(response: httpx.Response, status: HTTPStatus, action: str) -> httpx.Response:
    """Return the response if it has the expected status, else raise ApiError."""
    if response.status_code != status:
        raise ApiError(action, response)
    return response


class BaseClient:
    """An endpoint group sending its requests through one shared AuthSession."""

    def __init__(self, session: AuthSession):
        self._session = session
