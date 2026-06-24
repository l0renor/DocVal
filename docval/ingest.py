"""Document ingestion: turn an uploaded file into a list of page images.

Images pass through as a single page; PDFs are rendered to one image per page.
Unsupported types, oversize files, and too-many-page documents are rejected with
a clear error (mapped to an HTTP status by the API layer).
"""

from __future__ import annotations

from dataclasses import dataclass

try:  # pragma: no cover - import shim
    import pymupdf
except ImportError:  # pragma: no cover
    import fitz as pymupdf

_IMAGE_TYPES = {"image/jpeg", "image/png"}
_IMAGE_EXTS = (".jpg", ".jpeg", ".png")


class IngestError(Exception):
    """A document could not be ingested. `status_code` is the HTTP status to return."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class IngestSettings:
    max_file_bytes: int = 20 * 1024 * 1024  # 20 MB
    max_pages: int = 20


def render_to_images(
    filename: str | None,
    content_type: str | None,
    data: bytes,
    settings: IngestSettings | None = None,
) -> list[bytes]:
    settings = settings or IngestSettings()

    if len(data) > settings.max_file_bytes:
        raise IngestError(
            f"File exceeds the maximum size of {settings.max_file_bytes} bytes",
            status_code=413,
        )

    ctype = (content_type or "").split(";")[0].strip().lower()
    name = (filename or "").lower()

    if ctype in _IMAGE_TYPES or name.endswith(_IMAGE_EXTS):
        return [data]

    if ctype == "application/pdf" or name.endswith(".pdf"):
        return _render_pdf(data, settings)

    raise IngestError(
        f"Unsupported file type: {content_type or filename or 'unknown'}",
        status_code=400,
    )


def _render_pdf(data: bytes, settings: IngestSettings) -> list[bytes]:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - any parse failure is a bad upload
        raise IngestError(f"Could not read PDF: {exc}", status_code=400) from exc

    try:
        if doc.page_count > settings.max_pages:
            raise IngestError(
                f"PDF has {doc.page_count} pages; the maximum is {settings.max_pages}",
                status_code=400,
            )
        return [page.get_pixmap().tobytes("png") for page in doc]
    finally:
        doc.close()
