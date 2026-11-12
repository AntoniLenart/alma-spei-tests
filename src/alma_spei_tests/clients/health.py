"""Health probes (no authentication)."""

import httpx

from alma_spei_tests.clients.base import BaseClient
from alma_spei_tests.constants import ApiPath


class HealthClient(BaseClient):
    def live(self) -> httpx.Response:
        return self._session.get(ApiPath.HEALTH_LIVE)

    def ready(self) -> httpx.Response:
        return self._session.get(ApiPath.HEALTH_READY)

    def get(self, path: str) -> httpx.Response:
        """GET an arbitrary path, e.g. an unknown API route."""
        return self._session.get(path)
