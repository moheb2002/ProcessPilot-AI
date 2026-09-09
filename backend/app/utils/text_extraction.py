"""Text extraction helpers for PDF, DOCX and plain-text uploads."""

from __future__ import annotations

import io

from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_EXTRACTED_CHARS = 200_000


def extract_text(content: bytes, filename: str, content_type: str) -> str | None:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    try:
        if suffix == "pdf" or content_type == "application/pdf":
            return _truncate(_from_pdf(content))
        if suffix == "docx":
            return _truncate(_from_docx(content))
        if suffix == "txt" or content_type.startswith("text/"):
            return _truncate(content.decode("utf-8", errors="replace"))
    except Exception:  # extraction is best-effort; the upload itself must still succeed
        logger.warning("text_extraction_failed", extra={"document_name": filename}, exc_info=True)
    return None


def _truncate(text: str) -> str:
    return text[:MAX_EXTRACTED_CHARS].strip()


def _from_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _from_docx(content: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs)
