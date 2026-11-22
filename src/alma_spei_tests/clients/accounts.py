"""Account administration endpoints (administrators only)."""

import httpx

from alma_spei_tests.clients.base import BaseClient
from alma_spei_tests.constants import ApiPath
from alma_spei_tests.http import HeaderOverrides


class AccountsClient(BaseClient):
    @staticmethod
    def account_path(account_id: str) -> str:
        return f"{ApiPath.ACCOUNTS}/{account_id}"

    def list(self) -> httpx.Response:
        return self._session.get(ApiPath.ACCOUNTS)

    def create(
        self,
        username: str,
        display_name: str,
        *,
        administrator: bool,
        headers: HeaderOverrides | None = None,
    ) -> httpx.Response:
        return self._session.post(
            ApiPath.ACCOUNTS,
            json={
                "username": username,
                "display-name": display_name,
                "administrator": administrator,
            },
            headers=headers,
        )

    def edit(
        self,
        account_id: str,
        display_name: str,
        *,
        active: bool,
        administrator: bool,
        headers: HeaderOverrides | None = None,
    ) -> httpx.Response:
        return self._session.patch(
            self.account_path(account_id),
            json={"display-name": display_name, "active": active, "administrator": administrator},
            headers=headers,
        )

    def reset_password(
        self, account_id: str, *, headers: HeaderOverrides | None = None
    ) -> httpx.Response:
        # The backend validates the body as a closed, empty map.
        return self._session.post(
            f"{self.account_path(account_id)}/reset-password", json={}, headers=headers
        )
