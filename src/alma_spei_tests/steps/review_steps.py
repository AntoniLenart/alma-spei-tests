"""Reusable steps for review decisions, donor proposals and previews (task 38).

Every review write carries the versions the reviewer last saw. The workflow
steps here read them first (``read_versions``) so a test states only the
decision it means; the raw steps take a ready payload for negative tests.
"""

from collections.abc import Mapping, Sequence
from http import HTTPStatus
from typing import Any

import httpx

from alma_spei_tests.clients import AlmaSpeiApi, expect_status
from alma_spei_tests.data import ReviewVersions, RowDecision, proposal_payload
from alma_spei_tests.http import HeaderOverrides
from alma_spei_tests.steps import step

#: Bank statements are single-sheet: every staged row is on worksheet 1.
WORKSHEET = 1


# --- decisions ----------------------------------------------------------------
@step("Read the decision of row {row} of import {batch_id}")
def read_decision(api: AlmaSpeiApi, batch_id: str, row: int | str) -> httpx.Response:
    return api.imports.decision(batch_id, WORKSHEET, row)


@step("Read the review versions of row {row} of import {batch_id}")
def read_versions(api: AlmaSpeiApi, batch_id: str, row: int) -> ReviewVersions:
    """The batch, decision and (when reported) catalogue versions a write must carry."""
    body = expect_status(
        api.imports.decision(batch_id, WORKSHEET, row), HTTPStatus.OK, "Read row decision"
    ).json()
    decision = body["decision"]
    return ReviewVersions(
        batch_version=body["batch"]["version"],
        decision_version=decision["version"] if decision else 0,
        catalog_version=body.get("catalog-version"),
    )


@step("Submit a decision payload for row {row} of import {batch_id}")
def submit_decision(
    api: AlmaSpeiApi,
    batch_id: str,
    row: int | str,
    payload: Mapping[str, object],
    *,
    headers: HeaderOverrides | None = None,
) -> httpx.Response:
    return api.imports.save_decision(batch_id, WORKSHEET, row, payload, headers=headers)


@step("Save a '{decision.kind}' decision for row {row} of import {batch_id}")
def save_decision(
    api: AlmaSpeiApi, batch_id: str, row: int, decision: RowDecision
) -> httpx.Response:
    """Read the row's current versions, then save ``decision`` against them."""
    payload = decision.to_payload(read_versions(api, batch_id, row))
    return api.imports.save_decision(batch_id, WORKSHEET, row, payload)


@step("Decide row {row} of import {batch_id} ('{decision.kind}')")
def decide(api: AlmaSpeiApi, batch_id: str, row: int, decision: RowDecision) -> dict[str, Any]:
    """Setup step: the decision must be saved (200); returns the decision response."""
    return expect_status(
        save_decision(api, batch_id, row, decision), HTTPStatus.OK, "Save row decision"
    ).json()


@step("Decide every row of import {batch_id}")
def decide_rows(
    api: AlmaSpeiApi, batch_id: str, decisions: Sequence[RowDecision]
) -> dict[str, Any]:
    """Setup step: decision ``i`` for row ``i + 1``; returns the last response."""
    body: dict[str, Any] = {}
    for row, decision in enumerate(decisions, start=1):
        body = decide(api, batch_id, row, decision)
    return body


# --- donor proposals ----------------------------------------------------------
@step("Submit a donor proposal for import {batch_id}")
def submit_proposal(
    api: AlmaSpeiApi,
    batch_id: str,
    payload: Mapping[str, object],
    *,
    headers: HeaderOverrides | None = None,
) -> httpx.Response:
    return api.imports.create_proposal(batch_id, payload, headers=headers)


@step("Propose donor '{profile[name]}' for import {batch_id}")
def propose_donor(api: AlmaSpeiApi, batch_id: str, profile: Mapping[str, object]) -> httpx.Response:
    """Propose a new donor against the batch and catalogue versions read just before."""
    versions = read_versions(api, batch_id, 1)
    payload = proposal_payload(profile, versions.batch_version, versions.catalog_version)
    return api.imports.create_proposal(batch_id, payload)


@step("Create donor proposal '{profile[name]}' for import {batch_id}")
def create_proposal(
    api: AlmaSpeiApi, batch_id: str, profile: Mapping[str, object]
) -> dict[str, Any]:
    """Setup step: the proposal must be created (201); returns the proposal."""
    response = propose_donor(api, batch_id, profile)
    return expect_status(response, HTTPStatus.CREATED, "Create donor proposal").json()["proposal"]


@step("Edit donor proposal {proposal_id} of import {batch_id}")
def update_proposal(
    api: AlmaSpeiApi, batch_id: str, proposal_id: str, payload: Mapping[str, object]
) -> httpx.Response:
    return api.imports.update_proposal(batch_id, proposal_id, payload)


@step("List the donor proposals of import {batch_id} {page}")
def list_proposals(api: AlmaSpeiApi, batch_id: str, **page: int | str) -> httpx.Response:
    return api.imports.proposals(batch_id, **page)


# --- lookups and history ------------------------------------------------------
@step("Look up existing payments for import {batch_id} with {params}")
def lookup_payments(
    api: AlmaSpeiApi, batch_id: str, params: Sequence[tuple[str, str | int]]
) -> httpx.Response:
    return api.imports.payments(batch_id, params)


@step("Read the review history of import {batch_id} {page}")
def read_review_events(api: AlmaSpeiApi, batch_id: str, **page: int | str) -> httpx.Response:
    return api.imports.review_events(batch_id, **page)


@step("Read the readiness blockers of import {batch_id} {page}")
def read_blockers(api: AlmaSpeiApi, batch_id: str, **page: int | str) -> httpx.Response:
    return api.imports.review_blockers(batch_id, **page)


# --- previews -----------------------------------------------------------------
@step("Request a preview of import {batch_id} at batch version {batch_version}")
def request_preview(
    api: AlmaSpeiApi,
    batch_id: str,
    batch_version: int,
    *,
    headers: HeaderOverrides | None = None,
) -> httpx.Response:
    return api.imports.create_preview(batch_id, {"batch-version": batch_version}, headers=headers)


@step("Prepare a preview of import {batch_id}")
def prepare_preview(api: AlmaSpeiApi, batch_id: str) -> httpx.Response:
    """Request a preview at the batch version read just before."""
    return request_preview(api, batch_id, read_versions(api, batch_id, 1).batch_version)


@step("Create a ready preview of import {batch_id}")
def create_preview(api: AlmaSpeiApi, batch_id: str) -> dict[str, Any]:
    """Setup step: the preview must be created (201); returns the preview response."""
    return expect_status(
        prepare_preview(api, batch_id), HTTPStatus.CREATED, "Create import preview"
    ).json()


@step("Read preview {preview_id} of import {batch_id}")
def read_preview(api: AlmaSpeiApi, batch_id: str, preview_id: str) -> httpx.Response:
    return api.imports.preview(batch_id, preview_id)


@step("Read the planned effects of preview {preview_id} {page}")
def read_preview_items(
    api: AlmaSpeiApi, batch_id: str, preview_id: str, **page: int | str
) -> httpx.Response:
    return api.imports.preview_items(batch_id, preview_id, **page)
