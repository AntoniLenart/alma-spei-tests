"""Reusable steps for donor profiles."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

import httpx

from alma_spei_tests.clients import AlmaSpeiApi, expect_status
from alma_spei_tests.clients.donors import QueryParams
from alma_spei_tests.data import DonorProfile
from alma_spei_tests.http import HeaderOverrides
from alma_spei_tests.steps import step


@step("Submit a new donor")
def request_create(
    api: AlmaSpeiApi, payload: Mapping[str, object], *, headers: HeaderOverrides | None = None
) -> httpx.Response:
    return api.donors.create(payload, headers=headers)


@step("Submit a raw JSON-typed body to POST /api/donors")
def request_create_with_content(api: AlmaSpeiApi, content: bytes) -> httpx.Response:
    return api.donors.create_with_content(content)


@step("Create donor '{profile.name}'")
def create_donor(api: AlmaSpeiApi, profile: DonorProfile) -> dict[str, Any]:
    """Create the donor and return it (setup step: fails loudly if not 201)."""
    response = expect_status(
        api.donors.create(profile.to_payload()), HTTPStatus.CREATED, "Create donor"
    )
    return response.json()["donor"]


@step("Open donor card {donor_id}")
def get_donor(api: AlmaSpeiApi, donor_id: str, **page: int) -> httpx.Response:
    return api.donors.get(donor_id, **page)


@step("Update donor {donor_id}")
def update_donor(api: AlmaSpeiApi, donor_id: str, payload: Mapping[str, object]) -> httpx.Response:
    return api.donors.update(donor_id, payload)


@step("Read the change history of donor {donor_id}")
def get_history(api: AlmaSpeiApi, donor_id: str, **page: int) -> httpx.Response:
    return api.donors.history(donor_id, **page)


@step("List donors {query}")
def list_donors(api: AlmaSpeiApi, **query: str | int) -> httpx.Response:
    return api.donors.list(**query)


@step("List donors with raw query {params}")
def list_donors_with(api: AlmaSpeiApi, params: QueryParams) -> httpx.Response:
    return api.donors.list_with(params)


@step("List donors tagged {tag}")
def list_tagged(api: AlmaSpeiApi, tag: str, **query: str | int) -> list[dict[str, Any]]:
    """Donors whose name contains ``tag`` (setup/verification helper)."""
    response = expect_status(api.donors.list(search=tag, **query), HTTPStatus.OK, "List donors")
    return response.json()["donors"]
