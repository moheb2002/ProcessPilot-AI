"""Document upload service: validation, storage and text extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_correlation_id, get_logger
from app.models.document import UploadedDocument
from app.repositories import AuditRepository, DocumentRepository
from app.schemas.report import DocumentRead
from app.schemas.user import CurrentUser
from app.services.storage import StorageBackend
from app.utils.text_extraction import extract_text

logger = get_logger(__name__)

TEXT_PREVIEW_CHARS = 500


class DocumentService:
    def __init__(
        self,
        *,
        storage: StorageBackend,
        document_repo: DocumentRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._storage = storage
        self._document_repo = document_repo
        self._audit_repo = audit_repo

    async def upload(self, file: UploadFile, user: CurrentUser) -> DocumentRead:
        filename = Path(file.filename or "").name
        if not filename:
            raise ValidationError("A filename is required.")

        suffix = Path(filename).suffix.lower()
        allowed_extensions = settings.allowed_upload_extensions
        if suffix not in allowed_extensions:
            allowed = ", ".join(sorted(allowed_extensions))
            raise ValidationError(f"Unsupported file type '{suffix}'. Allowed: {allowed}.")

        content = await file.read()
        if not content:
            raise ValidationError("The uploaded file is empty.")
        if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
            limit_mb = settings.MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
            raise ValidationError(f"File exceeds the maximum size of {limit_mb:.0f} MB.")

        content_type = file.content_type or "application/octet-stream"
        storage_uri = await self._storage.save(
            content=content, filename=filename, content_type=content_type
        )
        text = extract_text(content, filename, content_type)

        document = await self._document_repo.add(
            UploadedDocument(
                filename=filename,
                content_type=content_type,
                size_bytes=len(content),
                storage_backend=self._storage.name,
                storage_uri=storage_uri,
                extracted_text=text,
                owner_id=user.id,
            )
        )
        await self._audit_repo.record(
            action="document.uploaded",
            resource_type="document",
            resource_id=document.id,
            actor_id=user.id,
            correlation_id=get_correlation_id(),
            context={"filename": filename, "size_bytes": len(content)},
        )
        await self._document_repo.commit()

        return self._to_schema(document)

    async def get(self, document_id: str, user: CurrentUser) -> DocumentRead:
        document = await self._document_repo.get(document_id)
        if document is None or document.owner_id != user.id:
            raise NotFoundError(f"Document '{document_id}' was not found.")
        return self._to_schema(document)

    async def list(self, user: CurrentUser, *, limit: int, offset: int) -> tuple[list[DocumentRead], int]:
        items: Sequence[UploadedDocument] = await self._document_repo.list(
            limit=limit, offset=offset, owner_id=user.id
        )
        total = await self._document_repo.count(owner_id=user.id)
        return [self._to_schema(item) for item in items], total

    @staticmethod
    def _to_schema(document: UploadedDocument) -> DocumentRead:
        return DocumentRead(
            id=document.id,
            filename=document.filename,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
            storage_backend=document.storage_backend,
            storage_uri=document.storage_uri,
            text_preview=(document.extracted_text or "")[:TEXT_PREVIEW_CHARS] or None,
            created_at=document.created_at,
        )
