"""Schemas describing agent inputs and structured outputs."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import AliasChoices, ConfigDict, Field, field_serializer, field_validator, model_validator

from app.schemas.common import ORMModel
from app.schemas.roi import ROICalculationInput, ROIResult, ROIResultSchema, to_decimal

__all__ = [
    "AutomationOpportunity",
    "AutomationPlan",
    "Bottleneck",
    "BottleneckReport",
    "Effort",
    "ExecutiveReport",
    "ProcessAnalysis",
    "ProcessStep",
    "ROICalculationInput",
    "ROIInput",
    "ROIResult",
    "ROIResultSchema",
    "Severity",
    "TokenUsage",
]


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Effort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def _coerce_enum(value: object, enum_cls: type[StrEnum], default: StrEnum) -> StrEnum:
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        for member in enum_cls:
            if member.value == normalized:
                return member
    return default


# --------------------------------------------------------------------------- #
# 1. Process Analyzer Agent
# --------------------------------------------------------------------------- #
class ProcessStep(ORMModel):
    order: int = Field(default=1, ge=1)
    name: str
    description: str = ""
    actor: str = ""
    system: str = ""
    is_manual: bool = False
    estimated_minutes: float | None = Field(default=None, ge=0)


class ProcessAnalysis(ORMModel):
    process_name: str = ""
    actors: list[str] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    steps: list[ProcessStep] = Field(min_length=1)
    approvals: list[str] = Field(default_factory=list)
    manual_tasks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_step_sequence(self) -> "ProcessAnalysis":
        expected_orders = list(range(1, len(self.steps) + 1))
        if [step.order for step in self.steps] != expected_orders:
            raise ValueError("step order must be contiguous and start at 1")
        return self


# --------------------------------------------------------------------------- #
# 2. Bottleneck Detection Agent
# --------------------------------------------------------------------------- #
class Bottleneck(ORMModel):
    title: str = Field(min_length=1)
    severity: Severity = Severity.MEDIUM
    impact: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)

    @field_validator("severity", mode="before")
    @classmethod
    def _normalize_severity(cls, value: object) -> object:
        return _coerce_enum(value, Severity, Severity.MEDIUM)


class BottleneckReport(ORMModel):
    bottlenecks: list[Bottleneck] = Field(default_factory=list, max_length=7)


# --------------------------------------------------------------------------- #
# 3. Automation Advisor Agent
# --------------------------------------------------------------------------- #
class AutomationOpportunity(ORMModel):
    solution: str = Field(min_length=1)
    technology: str = Field(min_length=1)
    business_value: str = Field(min_length=1)
    implementation_effort: Effort = Effort.MEDIUM

    @field_validator("implementation_effort", mode="before")
    @classmethod
    def _normalize_effort(cls, value: object) -> object:
        return _coerce_enum(value, Effort, Effort.MEDIUM)


class AutomationPlan(ORMModel):
    opportunities: list[AutomationOpportunity] = Field(default_factory=list, max_length=6)


# --------------------------------------------------------------------------- #
# 4. ROI Agent
# --------------------------------------------------------------------------- #
class ROIInput(ORMModel):
    """Lenient, API-facing baseline metrics.

    Kept permissive so an analysis can run without financial data. Call
    :meth:`to_calculation_input` to obtain the strictly validated
    :class:`~app.schemas.roi.ROICalculationInput` that the ROI service requires.
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    monthly_volume: int = Field(default=0, ge=0, le=10_000_000)
    minutes_per_case: Decimal = Field(
        default=Decimal(0),
        ge=0,
        le=100_000,
        validation_alias=AliasChoices("minutes_per_case", "minutes_per_transaction"),
    )
    hourly_cost: Decimal = Field(
        default=Decimal(0),
        ge=0,
        le=10_000,
        validation_alias=AliasChoices("hourly_cost", "employee_hourly_rate"),
    )
    automation_potential_percentage: Decimal | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Share of current effort expected to be automated, 0-100. "
            "When omitted the ROI agent estimates it once and reuses it everywhere."
        ),
        validation_alias=AliasChoices(
            "automation_potential_percentage", "automation_potential", "reduction_percentage"
        ),
    )
    implementation_cost: Decimal = Field(default=Decimal(0), ge=0)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_automation_rate(cls, data: object) -> object:
        """Accept the legacy 0-1 ``automation_rate`` and normalise it to a percentage."""
        if isinstance(data, dict) and "automation_rate" in data:
            rate = data.get("automation_rate")
            if rate is not None and data.get("automation_potential_percentage") is None:
                data = {**data, "automation_potential_percentage": to_decimal(rate) * 100}
        return data

    @field_validator(
        "minutes_per_case", "hourly_cost", "automation_potential_percentage", "implementation_cost",
        mode="before",
    )
    @classmethod
    def _as_decimal(cls, value: object) -> object:
        return value if value is None else to_decimal(value)

    @field_serializer("minutes_per_case", "hourly_cost", "implementation_cost")
    def _serialize_decimal(self, value: Decimal) -> float:
        return float(value)

    @field_serializer("automation_potential_percentage")
    def _serialize_optional_decimal(self, value: Decimal | None) -> float | None:
        return None if value is None else float(value)

    @property
    def has_baseline_metrics(self) -> bool:
        """True when volume and handling time are sufficient to calculate ROI."""
        return self.monthly_volume > 0 and self.minutes_per_case > 0

    def to_calculation_input(self, automation_potential_percentage: Decimal) -> ROICalculationInput:
        """Build the strict calculation input. Raises when metrics are missing."""
        return ROICalculationInput(
            monthly_volume=self.monthly_volume,
            minutes_per_case=self.minutes_per_case,
            hourly_cost=self.hourly_cost,
            automation_potential_percentage=automation_potential_percentage,
            implementation_cost=self.implementation_cost,
        )


# --------------------------------------------------------------------------- #
# 5. Executive Summary Agent
# --------------------------------------------------------------------------- #
class ExecutiveReport(ORMModel):
    report: str = ""


class TokenUsage(ORMModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )
