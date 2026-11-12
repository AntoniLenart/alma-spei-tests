"""Reusable steps for the health endpoints."""

import httpx

from alma_spei_tests.clients import AlmaSpeiApi
from alma_spei_tests.constants import ApiPath
from alma_spei_tests.steps import step


@step("Request liveness probe GET /api/health/live")
def request_liveness(api: AlmaSpeiApi) -> httpx.Response:
    return api.health.live()


@step("Request readiness probe GET /api/health/ready")
def request_readiness(api: AlmaSpeiApi) -> httpx.Response:
    return api.health.ready()


@step("Request unknown API route GET {path}")
def request_unknown_api_route(api: AlmaSpeiApi, path: str = ApiPath.UNKNOWN) -> httpx.Response:
    return api.health.get(path)
