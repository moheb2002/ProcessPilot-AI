"""Deterministic ROI calculation result."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class ROIResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roi_results"

    monthly_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    minutes_per_transaction: Mapped[float] = mapped_column(Float, nullable=False)
    employee_hourly_rate: Mapped[float] = mapped_column(Float, nullable=False)
    automation_rate: Mapped[float] = mapped_column(Float, nullable=False)

    current_hours: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_hours_saved: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_savings: Mapped[float] = mapped_column(Float, nullable=False)
    annual_savings: Mapped[float] = mapped_column(Float, nullable=False)
    roi_score: Mapped[float] = mapped_column(Float, nullable=False)

    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    analysis: Mapped["Analysis"] = relationship(back_populates="roi_result", lazy="selectin")
