"""Canonical ROI schemas — the single source of truth for every ROI number.

Design rules enforced here:

* Calculations are performed with :class:`~decimal.Decimal` so currency never
  drifts through binary-float error.
* No rounding happens during calculation. Rounding is applied exactly once,
  when the result object is built for serialisation/presentation.
* Rounding precision: hours <= 2 dp, currency == 2 dp, percentages <= 1 dp.
* Small positive values never collapse to zero (0.29 h stays 0.29 h).
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from pydantic import (
    AliasChoices,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from app.schemas.common import ORMModel

MINUTES_PER_HOUR = Decimal(60)
MONTHS_PER_YEAR = Decimal(12)
PERCENT = Decimal(100)

_HOURS_EXP = Decimal("0.01")
_CURRENCY_EXP = Decimal("0.01")
_PERCENT_EXP = Decimal("0.1")


def to_decimal(value: Any) -> Decimal:
    """Convert any numeric input to ``Decimal`` without float artefacts."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):  # bool is an int subclass; reject it explicitly
        raise TypeError("boolean is not a valid numeric value")
    return Decimal(str(value))


def round_hours(value: Decimal) -> Decimal:
    """Hours: at most two decimal places, trailing zeros removed."""
    quantised = to_decimal(value).quantize(_HOURS_EXP, rounding=ROUND_HALF_UP)
    normalised = quantised.normalize()
    # ``normalize`` can yield exponent notation for integers (8E+1); re-expand it.
    return normalised if normalised.as_tuple().exponent <= 0 else normalised.quantize(Decimal(1))


def round_currency(value: Decimal) -> Decimal:
    """Currency: exactly two decimal places, always."""
    return to_decimal(value).quantize(_CURRENCY_EXP, rounding=ROUND_HALF_UP)


def round_percentage(value: Decimal) -> Decimal:
    """Percentage: at most one decimal place, trailing zeros removed."""
    quantised = to_decimal(value).quantize(_PERCENT_EXP, rounding=ROUND_HALF_UP)
    normalised = quantised.normalize()
    return normalised if normalised.as_tuple().exponent <= 0 else normalised.quantize(Decimal(1))


class ROICalculationInput(ORMModel):
    """Strictly validated baseline metrics required to calculate ROI.

    Legacy field names (``minutes_per_transaction``, ``employee_hourly_rate``)
    are accepted as validation aliases so existing clients keep working.
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    monthly_volume: int = Field(
        gt=0,
        le=10_000_000,
        description="Number of process instances handled per month. Must be greater than zero.",
    )
    minutes_per_case: Decimal = Field(
        gt=0,
        le=100_000,
        validation_alias=AliasChoices("minutes_per_case", "minutes_per_transaction"),
        description="Average hands-on minutes spent per case. Must be greater than zero.",
    )
    hourly_cost: Decimal = Field(
        ge=0,
        le=10_000,
        validation_alias=AliasChoices("hourly_cost", "employee_hourly_rate"),
        description="Fully loaded hourly cost of the people performing the work.",
    )
    automation_potential_percentage: Decimal = Field(
        ge=0,
        le=100,
        validation_alias=AliasChoices(
            "automation_potential_percentage", "automation_potential", "reduction_percentage"
        ),
        description="Share of current effort automation is expected to remove (0-100).",
    )
    implementation_cost: Decimal = Field(default=Decimal(0), ge=0)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_automation_rate(cls, data: Any) -> Any:
        """Accept the legacy 0-1 ``automation_rate`` and normalise it to a percentage."""
        if isinstance(data, dict) and "automation_rate" in data:
            rate = data.get("automation_rate")
            if rate is not None and data.get("automation_potential_percentage") is None:
                data = {**data, "automation_potential_percentage": to_decimal(rate) * 100}
        return data

    @field_validator(
        "minutes_per_case",
        "hourly_cost",
        "automation_potential_percentage",
        "implementation_cost",
        mode="before",
    )
    @classmethod
    def _as_decimal(cls, value: Any) -> Any:
        if value is None:
            return value
        try:
            return to_decimal(value)
        except (TypeError, ArithmeticError, ValueError) as exc:
            raise ValueError(f"'{value}' is not a valid numeric value.") from exc

    @field_serializer(
        "minutes_per_case", "hourly_cost", "automation_potential_percentage", "implementation_cost"
    )
    def _serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class ROIRawValues(ORMModel):
    """Unrounded intermediate values. Never serialised to API clients."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    current_monthly_hours: Decimal
    estimated_hours_saved: Decimal
    remaining_monthly_hours: Decimal
    monthly_productivity_value: Decimal
    annual_productivity_value: Decimal
    automation_potential_percentage: Decimal


class ROIResult(ORMModel):
    """Presentation-ready ROI values. This object is the single source of truth.

    The executive report, the analysis response and any persisted row must all
    be derived from one instance of this model. Nothing downstream — least of
    all an LLM — may recalculate or restate these numbers.
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore", populate_by_name=True)

    current_monthly_hours: Decimal = Decimal(0)
    estimated_hours_saved: Decimal = Decimal(0)
    remaining_monthly_hours: Decimal = Decimal(0)
    monthly_productivity_value: Decimal = Decimal("0.00")
    annual_productivity_value: Decimal = Decimal("0.00")
    automation_potential_percentage: Decimal = Decimal(0)
    calculation_method: str = ""
    assumptions: list[str] = Field(default_factory=list)

    # --- Backwards-compatible aliases retained for existing clients/storage ---
    current_hours: Decimal = Decimal(0)
    monthly_savings: Decimal = Decimal("0.00")
    annual_savings: Decimal = Decimal("0.00")
    roi_score: Decimal = Decimal(0)

    @model_validator(mode="after")
    def _apply_presentation_rounding(self) -> "ROIResult":
        """Normalise precision so a value is identical however it was rehydrated.

        Values loaded back from float storage (``80.0``) must render exactly as
        they did when first calculated (``80``), otherwise the analysis and the
        report would disagree on formatting even when the numbers match.
        """
        object.__setattr__(
            self, "current_monthly_hours", round_hours(self.current_monthly_hours)
        )
        object.__setattr__(
            self, "estimated_hours_saved", round_hours(self.estimated_hours_saved)
        )
        object.__setattr__(
            self, "remaining_monthly_hours", round_hours(self.remaining_monthly_hours)
        )
        object.__setattr__(
            self, "monthly_productivity_value", round_currency(self.monthly_productivity_value)
        )
        object.__setattr__(
            self, "annual_productivity_value", round_currency(self.annual_productivity_value)
        )
        object.__setattr__(
            self,
            "automation_potential_percentage",
            round_percentage(self.automation_potential_percentage),
        )
        object.__setattr__(self, "current_hours", round_hours(self.current_hours))
        object.__setattr__(self, "monthly_savings", round_currency(self.monthly_savings))
        object.__setattr__(self, "annual_savings", round_currency(self.annual_savings))
        object.__setattr__(self, "roi_score", round_percentage(self.roi_score))
        return self

    @field_serializer(
        "current_monthly_hours",
        "estimated_hours_saved",
        "remaining_monthly_hours",
        "automation_potential_percentage",
        "current_hours",
        "roi_score",
    )
    def _serialize_number(self, value: Decimal) -> float:
        return float(value)

    @field_serializer(
        "monthly_productivity_value",
        "annual_productivity_value",
        "monthly_savings",
        "annual_savings",
    )
    def _serialize_currency(self, value: Decimal) -> float:
        # Currency is quantised to exactly 2 dp before it reaches this point,
        # so the float conversion is lossless at JSON precision.
        return float(value)

    def fingerprint(self) -> tuple[Decimal, ...]:
        """Values that must remain identical between analysis and report."""
        return (
            self.current_monthly_hours,
            self.estimated_hours_saved,
            self.remaining_monthly_hours,
            self.monthly_productivity_value,
            self.annual_productivity_value,
            self.automation_potential_percentage,
        )

    def as_prompt_facts(self) -> dict[str, str]:
        """Pre-formatted strings for prompt embedding — never raw maths inputs."""
        return {
            "current_monthly_hours": f"{self.current_monthly_hours}",
            "estimated_hours_saved": f"{self.estimated_hours_saved}",
            "remaining_monthly_hours": f"{self.remaining_monthly_hours}",
            "monthly_productivity_value": f"{self.monthly_productivity_value}",
            "annual_productivity_value": f"{self.annual_productivity_value}",
            "automation_potential_percentage": f"{self.automation_potential_percentage}",
        }


#: Compatibility alias — the historical name used across the agent layer.
ROIResultSchema = ROIResult
