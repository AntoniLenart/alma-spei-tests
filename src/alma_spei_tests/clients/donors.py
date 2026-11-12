"""Donor profile endpoints (any authenticated, password-rotated user)."""

from collections.abc import Mapping

import httpx

from alma_spei_tests.clients.base import BaseClient
from alma_spei_tests.constants import ApiPath, ContentType, Header
from alma_spei_tests.http import HeaderOverrides

#: Query values as httpx accepts them; a list of pairs allows repeated keys.
QueryParams = Mapping[str, str | int] | list[tuple[str, str]]


def _kebab(query: Mapping[str, str | int]) -> dict[str, str | int]:
    """``sort_by=...`` -> ``sort-by=...`` so callers can use Python keywords."""
    return {key.replace("_", "-"): value for key, value in query.items()}


class DonorsClient(BaseClient):
    @staticmethod
    def donor_path(donor_id: str) -> str:
        return f"{ApiPath.DONORS}/{donor_id}"

    def list(self, **query: str | int) -> httpx.Response:
        """List donors; keywords map to query params (``sort_by`` -> ``sort-by``)."""
        return self.list_with(_kebab(query))

    def list_with(self, params: QueryParams) -> httpx.Response:
        """List with raw query params (for invalid/duplicate parameter tests)."""
        return self._session.get(ApiPath.DONORS, params=params)

    def create(
        self, payload: Mapping[str, object], *, headers: HeaderOverrides | None = None
    ) -> httpx.Response:
        return self._session.post(ApiPath.DONORS, json=payload, headers=headers)

    def create_with_content(self, content: bytes) -> httpx.Response:
        """POST a raw JSON-typed body (for malformed/oversized body tests)."""
        return self._session.post(
            ApiPath.DONORS, content=content, headers={Header.CONTENT_TYPE: ContentType.JSON}
        )

    def get(self, donor_id: str, **page: int) -> httpx.Response:
        """Donor card: profile plus a page of donations (``limit``/``offset``)."""
        return self._session.get(self.donor_path(donor_id), params=page)

    def update(self, donor_id: str, payload: Mapping[str, object]) -> httpx.Response:
        """Replace the profile; ``payload`` must carry the current ``version``."""
        return self._session.put(self.donor_path(donor_id), json=payload)

    def history(self, donor_id: str, **page: int) -> httpx.Response:
        return self._session.get(f"{self.donor_path(donor_id)}/history", params=page)
