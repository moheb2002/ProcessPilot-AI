"""Deterministic ROI calculation result."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class ROIResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Persisted mirror of the validated :class:`app.schemas.roi.ROIResult`.

    Values are stored exactly as calculated by :mod:`app.services.roi_service`.
    Nothing re-derives them on read.
    """

    __tablename__ = "roi_results"

    # --- inputs ---
    monthly_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    minutes_per_transaction: Mapped[float] = mapped_column(Float, nullable=False)
    employee_hourly_rate: Mapped[float] = mapped_column(Float, nullable=False)
    automation_rate: Mapped[float] = mapped_column(Float, nullable=False)
    automation_potential_percentage: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )

    # --- outputs (single source of truth) ---
    current_hours: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_hours_saved: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_monthly_hours: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    monthly_savings: Mapped[float] = mapped_column(Float, nullable=False)
    annual_savings: Mapped[float] = mapped_column(Float, nullable=False)
    roi_score: Mapped[float] = mapped_column(Float, nullable=False)
    calculation_method: Mapped[str] = mapped_column(Text, default="", nullable=False)
    assumptions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    analysis: Mapped["Analysis"] = relationship(back_populates="roi_result", lazy="selectin")
