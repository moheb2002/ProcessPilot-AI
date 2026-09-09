"""Document upload endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.api.deps import CurrentUserDep, DocumentServiceDep, PaginationDep
from app.schemas.common import Page
from app.schemas.report import DocumentRead

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a supporting document (PDF, DOCX or TXT)",
)
async def upload_document(
    service: DocumentServiceDep,
    user: CurrentUserDep,
    file: Annotated[UploadFile, File(description="PDF, DOCX or TXT file, max 10 MB.")],
) -> DocumentRead:
    return await service.upload(file, user)


@router.get("", response_model=Page[DocumentRead], summary="List uploaded documents")
async def list_documents(
    service: DocumentServiceDep,
    user: CurrentUserDep,
    pagination: PaginationDep,
) -> Page[DocumentRead]:
    items, total = await service.list(user, limit=pagination.limit, offset=pagination.offset)
    return Page[DocumentRead](
        items=items, total=total, limit=pagination.limit, offset=pagination.offset
    )


@router.get("/{document_id}", response_model=DocumentRead, summary="Get document metadata")
async def get_document(
    document_id: str,
    service: DocumentServiceDep,
    user: CurrentUserDep,
) -> DocumentRead:
    return await service.get(document_id, user)
