"""Schemas describing agent inputs and structured outputs."""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ORMModel


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
    monthly_volume: int = Field(default=0, ge=0, le=10_000_000)
    minutes_per_transaction: float = Field(default=0, ge=0, le=100_000)
    employee_hourly_rate: float = Field(default=0, ge=0, le=10_000)
    automation_rate: float = Field(
        default=0.6, ge=0, le=1, description="Share of effort expected to be automated."
    )
    implementation_cost: float = Field(default=0, ge=0)


class ROIResultSchema(ORMModel):
    current_hours: float = 0
    estimated_hours_saved: float = 0
    monthly_savings: float = 0
    annual_savings: float = 0
    roi_score: float = 0


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
