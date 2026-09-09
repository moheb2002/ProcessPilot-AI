"""Automation recommendation produced by the Automation Advisor agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.analysis import Analysis


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"

    # --- legacy fields retained for existing consumers ---
    solution: Mapped[str] = mapped_column(String(255), nullable=False)
    technology: Mapped[str] = mapped_column(String(255), nullable=False)
    business_value: Mapped[str] = mapped_column(Text, nullable=False)
    implementation_effort: Mapped[str] = mapped_column(String(32), nullable=False)

    # --- scored recommendation fields ---
    reference: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    related_bottleneck_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    priority: Mapped[str] = mapped_column(String(32), default="Medium", nullable=False)
    business_impact: Mapped[str] = mapped_column(String(32), default="Medium", nullable=False)
    implementation_complexity: Mapped[str] = mapped_column(
        String(32), default="Medium", nullable=False
    )
    estimated_hours_saved_per_month: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False
    )
    estimated_monthly_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    estimated_annual_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recommended_technologies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    expected_benefits: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    implementation_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    implementation_timeframe_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    recommendation_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    score_explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)

    analysis_id: Mapped[str] = mapped_column(
        ForeignKey("analyses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    analysis: Mapped["Analysis"] = relationship(back_populates="recommendations", lazy="selectin")
