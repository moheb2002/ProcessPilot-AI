"""Agent 5 — produces a consultant-style Markdown executive report."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.prompts.templates import EXECUTIVE_SUMMARY_PROMPT
from app.schemas.agent import TokenUsage
from app.services.azure_openai import LLMClient


class ExecutiveSummaryAgent:
    """Text (not JSON) agent, so it does not extend :class:`BaseAgent`."""

    template = EXECUTIVE_SUMMARY_PROMPT

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def run(
        self,
        *,
        process_name: str,
        analysis: Any,
        bottlenecks: Any,
        opportunities: Any,
        roi: Any,
    ) -> tuple[str, TokenUsage]:
        system, user = self.template.render(
            process_name=process_name,
            process_analysis=BaseAgent.serialize(analysis),
            bottlenecks=BaseAgent.serialize(bottlenecks),
            opportunities=BaseAgent.serialize(opportunities),
            roi=BaseAgent.serialize(roi),
        )
        report, usage = await self._llm.complete_text(
            system=system, user=user, template_name=self.template.name
        )
        return report.strip(), usage
