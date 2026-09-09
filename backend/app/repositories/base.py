"""Generic async repository implementing shared CRUD behaviour."""

from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Persistence-agnostic CRUD operations for a single aggregate."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: str) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        order_by: Any | None = None,
        **filters: Any,
    ) -> Sequence[ModelT]:
        stmt: Select[tuple[ModelT]] = select(self.model).filter_by(**filters)
        stmt = stmt.order_by(order_by if order_by is not None else self.model.id)  # type: ignore[attr-defined]
        result = await self.session.scalars(stmt.limit(limit).offset(offset))
        return result.all()

    async def count(self, **filters: Any) -> int:
        stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        return int(await self.session.scalar(stmt) or 0)

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self.session.delete(entity)
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
