"""User account model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import Role
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis
    from app.models.document import UploadedDocument
    from app.models.process import Process


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=32), default=Role.EMPLOYEE, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    processes: Mapped[list["Process"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", lazy="selectin"
    )
    analyses: Mapped[list["Analysis"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", lazy="selectin"
    )
    documents: Mapped[list["UploadedDocument"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User {self.email} role={self.role}>"
