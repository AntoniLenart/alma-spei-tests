"""Reusable steps for the health endpoints."""

import httpx

from alma_spei_tests.api import ApiClient
from alma_spei_tests.steps import step

LIVE_PATH = "/api/health/live"
READY_PATH = "/api/health/ready"


@step("Request liveness probe GET /api/health/live")
def request_liveness(api: ApiClient) -> httpx.Response:
    return api.get(LIVE_PATH)


@step("Request readiness probe GET /api/health/ready")
def request_readiness(api: ApiClient) -> httpx.Response:
    return api.get(READY_PATH)


@step("Request unknown API route GET {path}")
def request_unknown_api_route(api: ApiClient, path: str = "/api/does-not-exist") -> httpx.Response:
    return api.get(path)
