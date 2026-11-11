"""Session endpoints: inspect, login, logout, password change."""

import httpx

from alma_spei_tests.clients.base import BaseClient
from alma_spei_tests.constants import ApiPath
from alma_spei_tests.http import HeaderOverrides


class AuthClient(BaseClient):
    def session(self) -> httpx.Response:
        """GET the current principal (or null) and the CSRF token; sets alma-csrf."""
        return self._session.get(ApiPath.AUTH_SESSION)

    def login(
        self, username: str, password: str, *, headers: HeaderOverrides | None = None
    ) -> httpx.Response:
        return self.login_with({"username": username, "password": password}, headers=headers)

    def login_with(self, body: object, *, headers: HeaderOverrides | None = None) -> httpx.Response:
        """POST an arbitrary login body (for validation tests)."""
        return self._session.post(ApiPath.AUTH_LOGIN, json=body, headers=headers)

    def change_password(self, current_password: str, new_password: str) -> httpx.Response:
        return self._session.post(
            ApiPath.AUTH_PASSWORD,
            json={"current-password": current_password, "password": new_password},
        )
