"""Agent 4 — estimates the automation potential, then delegates all maths.

The agent never performs arithmetic. It asks the model for a single input —
the share of effort automation can realistically remove — and hands that to
:mod:`app.services.roi_service`, which owns every ROI number in the system.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.logging import get_logger
from app.core.scoring_config import ROI_DEFAULTS
from app.prompts.templates import ROI_STRATEGY_PROMPT
from app.schemas.agent import ROIInput, TokenUsage
from app.schemas.insight import AutomationPotential
from app.schemas.roi import ROICalculationInput, ROIResult, round_percentage, to_decimal
from app.services.azure_openai import LLMClient
from app.services.roi_service import (
    CALCULATION_METHOD,
    calculate_roi,
    calculate_roi_raw,
    zero_roi,
)

logger = get_logger(__name__)

__all__ = [
    "AutomationRateEstimate",
    "ROIAgent",
    "ROIAgentResult",
    "build_calculation_input",
    "calculate_roi",
    "calculate_roi_raw",
    "calculate_roi_from_input",
]

_NO_METRICS_REASON = (
    "Monthly volume and minutes per case were not supplied, so no ROI could be calculated. "
    "Provide baseline metrics to quantify the business case."
)


class AutomationRateEstimate(BaseModel):
    """Structured output of the automation-potential prompt (a rate, not a result)."""

    automation_rate: float = Field(default=ROI_DEFAULTS.automation_rate, ge=0.0, le=1.0)
    rationale: str = ""
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("automation_rate", mode="before")
    @classmethod
    def _clamp(cls, value: Any) -> Any:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return ROI_DEFAULTS.automation_rate
        return min(max(numeric, 0.0), 1.0)

    @property
    def percentage(self) -> Decimal:
        return round_percentage(to_decimal(self.automation_rate) * 100)


class ROIAgentResult(BaseModel):
    """Everything the pipeline needs from the ROI stage, calculated exactly once."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    roi: ROIResult
    automation_potential: AutomationPotential
    calculation_input: ROICalculationInput | None = None


def calculate_roi_from_input(roi_input: ROIInput, percentage: Decimal) -> ROIResult:
    """Lenient API input -> strict calculation input -> canonical result."""
    calculation_input = build_calculation_input(roi_input, percentage)
    if calculation_input is None:
        return zero_roi(_NO_METRICS_REASON)
    return calculate_roi(calculation_input)


def build_calculation_input(
    roi_input: ROIInput, percentage: Decimal
) -> ROICalculationInput | None:
    """``None`` when baseline metrics are absent, so ROI is explicitly zero."""
    if not roi_input.has_baseline_metrics:
        return None
    return roi_input.to_calculation_input(percentage)


class ROIAgent:
    """Combines an LLM automation-potential estimate with deterministic financial maths."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(
        self,
        *,
        roi_input: ROIInput,
        analysis: Any = None,
        opportunities: Any = None,
        estimate_automation_rate: bool = True,
    ) -> tuple[ROIAgentResult, TokenUsage]:
        usage = TokenUsage()
        explanation: list[str] = []
        percentage = roi_input.automation_potential_percentage
        method = "Automation potential supplied by the caller."

        if percentage is None:
            percentage = ROI_DEFAULTS.automation_potential_percentage
            method = (
                f"No automation potential supplied; the configured conservative default of "
                f"{percentage}% was applied."
            )
            if estimate_automation_rate and roi_input.has_baseline_metrics:
                estimate, usage = await self._estimate_rate(roi_input, analysis, opportunities)
                percentage = estimate.percentage
                explanation = [estimate.rationale, *estimate.assumptions]
                method = (
                    "Automation potential estimated once by the automation-potential agent "
                    "and reused for every downstream calculation and report."
                )

        # Built once, then used for both the calculation and the persisted inputs.
        calculation_input = build_calculation_input(roi_input, percentage)
        roi = (
            calculate_roi(calculation_input)
            if calculation_input is not None
            else zero_roi(_NO_METRICS_REASON)
        )
        result = ROIAgentResult(
            roi=roi,
            automation_potential=AutomationPotential(
                percentage=roi.automation_potential_percentage,
                explanation=[item for item in explanation if item],
                calculation_method=f"{method} {CALCULATION_METHOD}",
            ),
            calculation_input=calculation_input,
        )
        return result, usage

    async def _estimate_rate(
        self, roi_input: ROIInput, analysis: Any, opportunities: Any
    ) -> tuple[AutomationRateEstimate, TokenUsage]:
        from app.agents.base import BaseAgent

        system, user = ROI_STRATEGY_PROMPT.render(
            process_analysis=BaseAgent.serialize(analysis or {}),
            opportunities=BaseAgent.serialize(opportunities or []),
            monthly_volume=roi_input.monthly_volume,
            minutes_per_transaction=roi_input.minutes_per_case,
            employee_hourly_rate=roi_input.hourly_cost,
        )
        payload, usage = await self._llm.complete_json(
            system=system, user=user, template_name=ROI_STRATEGY_PROMPT.name
        )
        return AutomationRateEstimate.model_validate(payload), usage
