"""Import endpoints (task 35): bank file upload and the staged-row report."""

from collections.abc import Mapping

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
        self, batch_id: str, version: int, filename: str, content: bytes, **kwargs: object
    ) -> httpx.Response:
        """Re-upload the original bytes as the next attempt of a failed batch."""
        retry_fields = {"retry-batch-id": batch_id, "version": str(version), "confirmed": "true"}
        return self.upload(filename, content, fields=retry_fields, **kwargs)

    def rows(self, batch_id: str, **page: int | str) -> httpx.Response:
        """A page of the batch's staged rows (``limit``/``offset``)."""
        return self._session.get(f"{self.batch_path(batch_id)}/rows", params=page)

    def rows_with(self, batch_id: str, params: list[tuple[str, str]]) -> httpx.Response:
        """Rows with raw query params (for invalid/duplicate parameter tests)."""
        return self._session.get(f"{self.batch_path(batch_id)}/rows", params=params)
