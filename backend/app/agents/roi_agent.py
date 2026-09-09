"""Agent 4 — deterministic ROI maths with an optional LLM-estimated automation rate."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.core.logging import get_logger
from app.prompts.templates import ROI_STRATEGY_PROMPT
from app.schemas.agent import ROIInput, ROIResultSchema, TokenUsage
from app.services.azure_openai import LLMClient

logger = get_logger(__name__)

MONTHS_PER_YEAR = 12
MINUTES_PER_HOUR = 60
#: ROI score is normalised against this annual saving so the 0-100 scale stays comparable.
ROI_SCORE_REFERENCE_SAVINGS = 250_000.0


class AutomationRateEstimate(BaseModel):
    automation_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    rationale: str = ""
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("automation_rate", mode="before")
    @classmethod
    def _clamp(cls, value: Any) -> Any:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.5
        return min(max(numeric, 0.0), 1.0)


def calculate_roi(roi_input: ROIInput) -> ROIResultSchema:
    """Pure function: no I/O, fully unit-testable."""
    current_hours = (
        roi_input.monthly_volume * roi_input.minutes_per_transaction
    ) / MINUTES_PER_HOUR
    hours_saved = current_hours * roi_input.automation_rate
    monthly_savings = hours_saved * roi_input.employee_hourly_rate
    annual_savings = monthly_savings * MONTHS_PER_YEAR

    if roi_input.implementation_cost > 0:
        roi_score = (
            (annual_savings - roi_input.implementation_cost) / roi_input.implementation_cost
        ) * 100
    else:
        roi_score = (annual_savings / ROI_SCORE_REFERENCE_SAVINGS) * 100

    return ROIResultSchema(
        current_hours=round(current_hours, 2),
        estimated_hours_saved=round(hours_saved, 2),
        monthly_savings=round(monthly_savings, 2),
        annual_savings=round(annual_savings, 2),
        roi_score=round(min(max(roi_score, 0.0), 100.0), 2),
    )


class ROIAgent:
    """Combines an LLM automation-rate estimate with deterministic financial maths."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(
        self,
        *,
        roi_input: ROIInput,
        analysis: Any = None,
        opportunities: Any = None,
        estimate_automation_rate: bool = True,
    ) -> tuple[ROIResultSchema, TokenUsage]:
        usage = TokenUsage()
        effective_input = roi_input

        if estimate_automation_rate and roi_input.monthly_volume > 0:
            estimate, usage = await self._estimate_rate(roi_input, analysis, opportunities)
            effective_input = roi_input.model_copy(
                update={"automation_rate": estimate.automation_rate}
            )

        return calculate_roi(effective_input), usage

    async def _estimate_rate(
        self, roi_input: ROIInput, analysis: Any, opportunities: Any
    ) -> tuple[AutomationRateEstimate, TokenUsage]:
        from app.agents.base import BaseAgent

        system, user = ROI_STRATEGY_PROMPT.render(
            process_analysis=BaseAgent.serialize(analysis or {}),
            opportunities=BaseAgent.serialize(opportunities or []),
            monthly_volume=roi_input.monthly_volume,
            minutes_per_transaction=roi_input.minutes_per_transaction,
            employee_hourly_rate=roi_input.employee_hourly_rate,
        )
        payload, usage = await self._llm.complete_json(
            system=system, user=user, template_name=ROI_STRATEGY_PROMPT.name
        )
        return AutomationRateEstimate.model_validate(payload), usage
