"""Uploaded supporting document metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class UploadedDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "uploaded_documents"

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    owner: Mapped["User"] = relationship(back_populates="documents", lazy="selectin")
