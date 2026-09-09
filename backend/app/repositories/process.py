"""Process, analysis, document and audit repositories."""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select

from app.models.analysis import Analysis
from app.models.audit import AuditLog
from app.models.document import UploadedDocument
from app.models.process import Process
from app.repositories.base import BaseRepository


class ProcessRepository(BaseRepository[Process]):
    model = Process


class AnalysisRepository(BaseRepository[Analysis]):
    model = Analysis

    async def list_for_owner(
        self, owner_id: str, *, limit: int = 50, offset: int = 0
    ) -> Sequence[Analysis]:
        stmt = (
            select(Analysis)
            .where(Analysis.owner_id == owner_id)
            .order_by(Analysis.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.scalars(stmt)).all()


class DocumentRepository(BaseRepository[UploadedDocument]):
    model = UploadedDocument

    async def get_many(self, document_ids: Sequence[str], owner_id: str) -> Sequence[UploadedDocument]:
        if not document_ids:
            return []
        stmt = select(UploadedDocument).where(
            UploadedDocument.id.in_(list(document_ids)),
            UploadedDocument.owner_id == owner_id,
        )
        return (await self.session.scalars(stmt)).all()


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def record(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        actor_id: str | None = None,
        correlation_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
            context=context or {},
        )
        return await self.add(entry)
