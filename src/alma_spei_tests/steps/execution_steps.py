"""Reusable steps for applying and undoing reviewed imports (task 39).

Committing needs, in order: a ready preview, a (synthetic) backup receipt bound
to that exact preview, and an explicit confirmation carrying every version the
reviewer saw. Undo carries the commit and the committed batch version. The
workflow steps build those requests from the server's own responses; the raw
steps send a ready payload for negative tests.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import httpx

from alma_spei_tests.clients import AlmaSpeiApi, expect_status
from alma_spei_tests.http import HeaderOverrides
from alma_spei_tests.steps import review_steps, step


@dataclass(frozen=True)
class CommittedImport:
    """A committed batch: the exact commit request and the outcome it returned."""

    request: dict[str, object]
    outcome: dict[str, Any]

    @property
    def batch_id(self) -> str:
        return self.outcome["batch"]["id"]

    @property
    def commit_id(self) -> str:
        return self.outcome["commit"]["id"]


# --- payloads -----------------------------------------------------------------
def backup_payload(preview: Mapping[str, Any]) -> dict[str, object]:
    """Backup request for a preview response (its batch and catalogue versions)."""
    return {
        "batch-version": preview["preview"]["batch-version"],
        "catalog-version": preview["preview"]["catalog-version"],
    }


def commit_payload(preview: Mapping[str, Any], backup: Mapping[str, Any]) -> dict[str, object]:
    """The explicit approval of exactly this preview, backed by this receipt."""
    snapshot = preview["preview"]
    return {
        "batch-id": snapshot["batch-id"],
        "batch-version": snapshot["batch-version"],
        "preview-id": snapshot["id"],
        "effect-digest": snapshot["effect-digest"],
        "catalog-version": snapshot["catalog-version"],
        "backup-id": backup["id"],
        "confirmed": True,
    }


def undo_payload(outcome: Mapping[str, Any]) -> dict[str, object]:
    """Undo of a committed outcome, at the batch version it reports."""
    return {
        "batch-id": outcome["batch"]["id"],
        "batch-version": outcome["batch"]["version"],
        "commit-id": outcome["commit"]["id"],
        "confirmed": True,
    }


# --- backup -------------------------------------------------------------------
@step("Request a backup receipt for preview {preview_id} of import {batch_id}")
def request_backup(
    api: AlmaSpeiApi, batch_id: str, preview_id: str, payload: Mapping[str, object]
) -> httpx.Response:
    return api.imports.backup(batch_id, preview_id, payload)


@step("Confirm a backup of the ready preview")
def confirm_backup(api: AlmaSpeiApi, preview: Mapping[str, Any]) -> dict[str, Any]:
    """Setup step: the synthetic backup must succeed (200); returns the receipt."""
    snapshot = preview["preview"]
    response = request_backup(api, snapshot["batch-id"], snapshot["id"], backup_payload(preview))
    return expect_status(response, HTTPStatus.OK, "Confirm import backup").json()["backup"]


# --- commit -------------------------------------------------------------------
@step("Submit an import commit")
def submit_commit(
    api: AlmaSpeiApi, payload: Mapping[str, object], *, headers: HeaderOverrides | None = None
) -> httpx.Response:
    return api.imports.commit(payload, headers=headers)


@step("Prepare, back up and approve import {batch_id}")
def approval_request(api: AlmaSpeiApi, batch_id: str) -> dict[str, object]:
    """A complete, valid commit request for the batch's decisions (nothing sent yet)."""
    preview = review_steps.create_preview(api, batch_id)
    return commit_payload(preview, confirm_backup(api, preview))


@step("Commit import {batch_id}")
def commit_import(api: AlmaSpeiApi, batch_id: str) -> CommittedImport:
    """Setup step: preview, back up and commit; the commit must answer 200."""
    request = approval_request(api, batch_id)
    response = expect_status(submit_commit(api, request), HTTPStatus.OK, "Commit import")
    return CommittedImport(request, response.json())


# --- undo ---------------------------------------------------------------------
@step("Submit an undo of the latest import")
def submit_undo(api: AlmaSpeiApi, payload: Mapping[str, object]) -> httpx.Response:
    return api.imports.undo_last(payload)


@step("Undo committed import {committed.batch_id}")
def undo_import(api: AlmaSpeiApi, committed: CommittedImport) -> dict[str, Any]:
    """Setup step: undo the commit at its current batch version; returns the outcome."""
    current = expect_status(
        api.imports.outcome(committed.batch_id), HTTPStatus.OK, "Read import outcome"
    ).json()
    response = expect_status(submit_undo(api, undo_payload(current)), HTTPStatus.OK, "Undo import")
    return response.json()


# --- reads --------------------------------------------------------------------
@step("Read the outcome of import {batch_id}")
def read_outcome(api: AlmaSpeiApi, batch_id: str) -> httpx.Response:
    return api.imports.outcome(batch_id)


@step("Read the applied effects of import {batch_id} {page}")
def read_commit_items(api: AlmaSpeiApi, batch_id: str, **page: int | str) -> httpx.Response:
    return api.imports.commit_items(batch_id, **page)


@step("Read the undo eligibility of import {batch_id}")
def read_undo_eligibility(api: AlmaSpeiApi, batch_id: str, **page: int | str) -> httpx.Response:
    return api.imports.undo_eligibility(batch_id, **page)


@step("Read the import history {page}")
def read_history(api: AlmaSpeiApi, **page: int | str) -> httpx.Response:
    return api.imports.history(**page)
