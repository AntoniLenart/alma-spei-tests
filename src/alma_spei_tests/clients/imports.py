"""Import endpoints (task 35): bank file upload and the staged-row report."""

from collections.abc import Mapping, Sequence

import httpx

from alma_spei_tests.clients.base import BaseClient
from alma_spei_tests.constants import ApiPath, CsvSeparator, ImportSource
from alma_spei_tests.http import HeaderOverrides

#: Content type of the uploaded file part (the server sniffs by extension).
FILE_PART_TYPE = "application/octet-stream"


class ImportsClient(BaseClient):
    @staticmethod
    def batch_path(batch_id: str) -> str:
        return f"{ApiPath.IMPORTS}/{batch_id}"

    def upload(
        self,
        filename: str,
        content: bytes,
        *,
        separator: CsvSeparator | None = CsvSeparator.SEMICOLON,
        source: str = ImportSource.BANK,
        fields: Mapping[str, str] | None = None,
        headers: HeaderOverrides | None = None,
    ) -> httpx.Response:
        """Multipart upload: ``source`` (+ ``separator`` for CSV) and one ``file`` part.

        ``fields`` adds or overrides form fields (retry fields, invalid extras);
        ``separator=None`` omits the separator field.
        """
        data = {"source": str(source)}
        if separator is not None:
            data["separator"] = str(separator)
        data.update(fields or {})
        return self._session.post(
            ApiPath.IMPORT_UPLOAD,
            data=data,
            files={"file": (filename, content, FILE_PART_TYPE)},
            headers=headers,
        )

    def retry(
        self,
        batch_id: str,
        version: int,
        filename: str,
        content: bytes,
        *,
        separator: CsvSeparator | None = CsvSeparator.SEMICOLON,
        headers: HeaderOverrides | None = None,
    ) -> httpx.Response:
        """Re-upload the original bytes as the next attempt of a failed batch."""
        retry_fields = {"retry-batch-id": batch_id, "version": str(version), "confirmed": "true"}
        return self.upload(
            filename, content, separator=separator, fields=retry_fields, headers=headers
        )

    def rows(self, batch_id: str, **page: int | str) -> httpx.Response:
        """A page of the batch's staged rows (``limit``/``offset``)."""
        return self._session.get(f"{self.batch_path(batch_id)}/rows", params=page)

    # --- review (task 37) ------------------------------------------------------
    def review_queue(self, **page: int | str) -> httpx.Response:
        """Bank batches awaiting review, newest first (``limit``/``offset``)."""
        return self.review_queue_with(list(page.items()))

    def review_queue_with(self, params: Sequence[tuple[str, str | int]]) -> httpx.Response:
        return self._session.get(ApiPath.IMPORT_REVIEW, params=params)

    def batch(self, batch_id: str, params: list[tuple[str, str]] | None = None) -> httpx.Response:
        """One bank batch's metadata (the endpoint accepts no query parameters)."""
        return self._session.get(self.batch_path(batch_id), params=params or [])

    def comparison(
        self,
        batch_id: str,
        worksheet: int | str,
        row: int | str,
        donor_id: str | None = None,
        *,
        params: list[tuple[str, str]] | None = None,
    ) -> httpx.Response:
        """A staged row next to one chosen donor; ``params`` replaces ``donor-id``."""
        query = params if params is not None else [("donor-id", donor_id or "")]
        path = f"{self.batch_path(batch_id)}/rows/{worksheet}/{row}/comparison"
        return self._session.get(path, params=query)

    def rows_with(self, batch_id: str, params: list[tuple[str, str]]) -> httpx.Response:
        """Rows with raw query params (for invalid/duplicate parameter tests)."""
        return self._session.get(f"{self.batch_path(batch_id)}/rows", params=params)
