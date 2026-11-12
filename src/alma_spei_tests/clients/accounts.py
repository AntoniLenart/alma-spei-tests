"""Account administration endpoints (administrators only)."""

import httpx

from alma_spei_tests.clients.base import BaseClient
from alma_spei_tests.constants import ApiPath


class AccountsClient(BaseClient):
    @staticmethod
    def account_path(account_id: str) -> str:
        return f"{ApiPath.ACCOUNTS}/{account_id}"

    def list(self) -> httpx.Response:
        return self._session.get(ApiPath.ACCOUNTS)

    def create(self, username: str, display_name: str, *, administrator: bool) -> httpx.Response:
        return self._session.post(
            ApiPath.ACCOUNTS,
            json={
                "username": username,
                "display-name": display_name,
                "administrator": administrator,
            },
        )

    def edit(
        self, account_id: str, display_name: str, *, active: bool, administrator: bool
    ) -> httpx.Response:
        return self._session.patch(
            self.account_path(account_id),
            json={"display-name": display_name, "active": active, "administrator": administrator},
        )

    def reset_password(self, account_id: str) -> httpx.Response:
        # The backend validates the body as a closed, empty map.
        return self._session.post(f"{self.account_path(account_id)}/reset-password", json={})
