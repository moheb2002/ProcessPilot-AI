"""Immutable audit trail entry."""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    action: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    actor_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
