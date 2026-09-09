"""Analysis aggregate: the result of a full agent pipeline run."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.process import Process
    from app.models.recommendation import Recommendation
    from app.models.roi import ROIResult
    from app.models.user import User


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Analysis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "analyses"

    status: Mapped[AnalysisStatus] = mapped_column(
        Enum(AnalysisStatus, native_enum=False, length=32),
        default=AnalysisStatus.PENDING,
        nullable=False,
    )
    process_name: Mapped[str] = mapped_column(String(255), nullable=False)
    analysis_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    bottlenecks_payload: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    opportunities_payload: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    #: Scored RecommendationDetail objects, stored verbatim so the report reuses them.
    recommendations_payload: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    automation_potential_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    confidence_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    quick_wins_payload: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)
    roadmap_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    report_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    executive_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    process_id: Mapped[str | None] = mapped_column(
        ForeignKey("processes.id", ondelete="SET NULL"), index=True, nullable=True
    )

    owner: Mapped["User"] = relationship(back_populates="analyses", lazy="selectin")
    process: Mapped["Process | None"] = relationship(back_populates="analyses", lazy="selectin")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", lazy="selectin"
    )
    roi_result: Mapped["ROIResult | None"] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
