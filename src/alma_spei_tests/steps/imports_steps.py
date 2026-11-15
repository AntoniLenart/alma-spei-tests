"""Reusable steps for bank imports (task 35)."""

from http import HTTPStatus
from typing import Any

import httpx

from alma_spei_tests.clients import AlmaSpeiApi, expect_status
from alma_spei_tests.constants import CsvSeparator, ImportSource
from alma_spei_tests.http import HeaderOverrides
from alma_spei_tests.steps import step


@step("Upload '{filename}' as a {source} import")
def upload(
    api: AlmaSpeiApi,
    filename: str,
    content: bytes,
    *,
    separator: CsvSeparator | None = CsvSeparator.SEMICOLON,
    source: str = ImportSource.BANK,
    fields: dict[str, str] | None = None,
    headers: HeaderOverrides | None = None,
) -> httpx.Response:
    return api.imports.upload(
        filename, content, separator=separator, source=source, fields=fields, headers=headers
    )


@step("Upload '{filename}' and expect it to be staged")
def upload_staged(
    api: AlmaSpeiApi,
    filename: str,
    content: bytes,
    *,
    separator: CsvSeparator | None = CsvSeparator.SEMICOLON,
) -> dict[str, Any]:
    """Setup step: the upload must answer 201; returns the upload report."""
    response = api.imports.upload(filename, content, separator=separator)
    return expect_status(response, HTTPStatus.CREATED, "Upload bank file").json()


@step("Retry failed import {batch_id} (version {version}) with '{filename}'")
def retry(
    api: AlmaSpeiApi, batch_id: str, version: int, filename: str, content: bytes
) -> httpx.Response:
    return api.imports.retry(batch_id, version, filename, content)


@step("Read staged rows of import {batch_id} {page}")
def read_rows(api: AlmaSpeiApi, batch_id: str, **page: int | str) -> httpx.Response:
    return api.imports.rows(batch_id, **page)


@step("Read staged rows of import {batch_id} with raw query {params}")
def read_rows_with(
    api: AlmaSpeiApi, batch_id: str, params: list[tuple[str, str]]
) -> httpx.Response:
    return api.imports.rows_with(batch_id, params)
