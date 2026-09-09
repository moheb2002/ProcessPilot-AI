"""Structured insight schemas: confidence, recommendations, Quick Wins, roadmap.

These models describe everything the API exposes *around* the ROI numbers.
Scores and selections are produced by deterministic backend services; the LLM
only supplies narrative text for the fields explicitly marked as narrative.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field, field_serializer, field_validator

from app.schemas.common import ORMModel


class Priority(StrEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class BusinessImpact(StrEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ImplementationEffort(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class ImplementationComplexity(StrEnum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Frequency(StrEnum):
    VERY_HIGH = "Very High"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class RiskReduction(StrEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class ConfidenceLevel(StrEnum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


def coerce_titlecase_enum(value: Any, enum_cls: type[StrEnum], default: StrEnum) -> StrEnum:
    """Accept any casing the model produces; fall back to a safe default."""
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        normalised = " ".join(value.strip().split()).casefold()
        for member in enum_cls:
            if member.value.casefold() == normalised:
                return member
    return default


class AnalysisConfidence(ORMModel):
    """Deterministic assessment of how much evidence backs the analysis."""

    score: float = Field(default=0.0, ge=0, le=100)
    level: ConfidenceLevel = ConfidenceLevel.LOW
    reasons: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)

    @field_validator("level", mode="before")
    @classmethod
    def _normalise_level(cls, value: Any) -> Any:
        return coerce_titlecase_enum(value, ConfidenceLevel, ConfidenceLevel.LOW)


class AutomationPotential(ORMModel):
    """The automation percentage that drives the ROI calculation."""

    percentage: Decimal = Field(default=Decimal(0), ge=0, le=100)
    explanation: list[str] = Field(default_factory=list)
    calculation_method: str = ""

    @field_serializer("percentage")
    def _serialize_percentage(self, value: Decimal) -> float:
        return float(value)


class RecommendationDetail(ORMModel):
    """A scored, prioritised automation recommendation."""

    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    id: str = ""
    title: str = ""
    description: str = ""
    related_bottleneck_ids: list[str] = Field(default_factory=list)
    priority: Priority = Priority.MEDIUM
    business_impact: BusinessImpact = BusinessImpact.MEDIUM
    implementation_effort: ImplementationEffort = ImplementationEffort.MEDIUM
    implementation_complexity: ImplementationComplexity = ImplementationComplexity.MEDIUM
    frequency: Frequency = Frequency.MEDIUM
    risk_reduction: RiskReduction = RiskReduction.MEDIUM
    estimated_hours_saved_per_month: Decimal = Field(default=Decimal(0), ge=0)
    estimated_monthly_value: Decimal = Field(default=Decimal("0.00"), ge=0)
    estimated_annual_value: Decimal = Field(default=Decimal("0.00"), ge=0)
    recommended_technologies: list[str] = Field(default_factory=list)
    expected_benefits: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    implementation_notes: str = ""
    implementation_timeframe_days: int = Field(default=30, ge=0, le=720)
    recommendation_score: float = Field(default=0.0, ge=0, le=100)
    score_explanation: str = ""

    @field_validator("priority", mode="before")
    @classmethod
    def _norm_priority(cls, value: Any) -> Any:
        return coerce_titlecase_enum(value, Priority, Priority.MEDIUM)

    @field_validator("business_impact", mode="before")
    @classmethod
    def _norm_impact(cls, value: Any) -> Any:
        return coerce_titlecase_enum(value, BusinessImpact, BusinessImpact.MEDIUM)

    @field_validator("implementation_effort", mode="before")
    @classmethod
    def _norm_effort(cls, value: Any) -> Any:
        return coerce_titlecase_enum(value, ImplementationEffort, ImplementationEffort.MEDIUM)

    @field_validator("implementation_complexity", mode="before")
    @classmethod
    def _norm_complexity(cls, value: Any) -> Any:
        return coerce_titlecase_enum(
            value, ImplementationComplexity, ImplementationComplexity.MEDIUM
        )

    @field_validator("frequency", mode="before")
    @classmethod
    def _norm_frequency(cls, value: Any) -> Any:
        return coerce_titlecase_enum(value, Frequency, Frequency.MEDIUM)

    @field_validator("risk_reduction", mode="before")
    @classmethod
    def _norm_risk(cls, value: Any) -> Any:
        return coerce_titlecase_enum(value, RiskReduction, RiskReduction.MEDIUM)

    @field_serializer(
        "estimated_hours_saved_per_month", "estimated_monthly_value", "estimated_annual_value"
    )
    def _serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class QuickWin(ORMModel):
    """A high-impact, low-friction recommendation deliverable within 30 days."""

    title: str = ""
    description: str = ""
    source_recommendation_id: str = ""
    priority: Priority = Priority.HIGH
    business_impact: BusinessImpact = BusinessImpact.HIGH
    implementation_effort: ImplementationEffort = ImplementationEffort.LOW
    estimated_hours_saved_per_month: Decimal = Field(default=Decimal(0), ge=0)
    recommended_technologies: list[str] = Field(default_factory=list)
    expected_outcome: str = ""
    implementation_timeframe: str = "0-30 days"
    dependencies: list[str] = Field(default_factory=list)

    @field_serializer("estimated_hours_saved_per_month")
    def _serialize_hours(self, value: Decimal) -> float:
        return float(value)


class RoadmapItem(ORMModel):
    title: str
    description: str = ""
    owner: str = ""
    recommendation_id: str = ""


class RoadmapPhase(ORMModel):
    name: str
    window: str
    objective: str = ""
    items: list[RoadmapItem] = Field(default_factory=list)


class Roadmap(ORMModel):
    """The 30-60-90 day implementation plan."""

    phases: list[RoadmapPhase] = Field(default_factory=list)


class ReportNarrative(ORMModel):
    """The only part of the executive report the LLM is allowed to author.

    Deliberately contains no numeric fields: every figure in the rendered report
    is injected by the backend from the validated ROIResult.
    """

    executive_summary: str = ""
    current_state_assessment: str = ""
    key_pain_points: list[str] = Field(default_factory=list)
    roi_interpretation: str = ""
    risks: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    executive_recommendation: str = ""
    confidence_commentary: str = ""


class ExecutiveReport(ORMModel):
    """The assembled executive report: deterministic numbers + LLM narrative."""

    markdown: str = ""
    narrative: ReportNarrative = Field(default_factory=ReportNarrative)
    roi_overridden: bool = Field(
        default=False,
        description="True when LLM-authored content conflicted with the validated ROI.",
    )
