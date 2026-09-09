"""Agent 5 — produces the *narrative* of the executive report.

The agent returns structured JSON containing prose only. Every number in the
final report is injected by :mod:`app.services.report_renderer` from the
validated :class:`~app.schemas.roi.ROIResult`, so the model has no opportunity
to recalculate or restate ROI.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.agents.base import BaseAgent
from app.core.logging import get_correlation_id, get_logger
from app.prompts.templates import EXECUTIVE_SUMMARY_PROMPT
from app.schemas.agent import TokenUsage
from app.schemas.insight import AnalysisConfidence, QuickWin, RecommendationDetail, ReportNarrative
from app.schemas.roi import ROIResult
from app.services.azure_openai import LLMClient

logger = get_logger(__name__)


class ExecutiveSummaryAgent:
    """Structured-output agent. Authors prose; never authors numbers."""

    template = EXECUTIVE_SUMMARY_PROMPT
    output_model = ReportNarrative

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(
        self,
        *,
        process_name: str,
        analysis: Any,
        bottlenecks: Any,
        recommendations: list[RecommendationDetail],
        quick_wins: list[QuickWin],
        confidence: AnalysisConfidence,
        roi: ROIResult,
    ) -> tuple[ReportNarrative, TokenUsage]:
        system, user = self.template.render(
            process_name=process_name,
            process_analysis=BaseAgent.serialize(analysis),
            bottlenecks=BaseAgent.serialize(bottlenecks),
            recommendations=BaseAgent.serialize(recommendations),
            quick_wins=BaseAgent.serialize(quick_wins),
            confidence=BaseAgent.serialize(confidence),
            roi_assumptions=BaseAgent.serialize(roi.assumptions),
            **roi.as_prompt_facts(),
        )
        payload, usage = await self._llm.complete_json(
            system=system, user=user, template_name=self.template.name
        )
        try:
            narrative = ReportNarrative.model_validate(payload)
        except PydanticValidationError as exc:
            # A malformed narrative must never block the deterministic report.
            logger.warning(
                "report_narrative_validation_failed",
                extra={
                    "correlation_id": get_correlation_id(),
                    "template": self.template.name,
                    "errors": exc.error_count(),
                },
            )
            narrative = ReportNarrative()
        return narrative, usage
