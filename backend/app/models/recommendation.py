"""Automation recommendation produced by the Automation Advisor agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"

    solution: Mapped[str] = mapped_column(String(255), nullable=False)
    technology: Mapped[str] = mapped_column(String(255), nullable=False)
    business_value: Mapped[str] = mapped_column(Text, nullable=False)
    implementation_effort: Mapped[str] = mapped_column(String(32), nullable=False)

    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    analysis: Mapped["Analysis"] = relationship(back_populates="recommendations", lazy="selectin")
