"""Business process model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.user import User


class Process(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "processes"

    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str | None] = mapped_column(String(128), nullable=True)
    process_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner: Mapped["User"] = relationship(back_populates="processes", lazy="selectin")
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="process", cascade="all, delete-orphan", lazy="selectin"
    )
