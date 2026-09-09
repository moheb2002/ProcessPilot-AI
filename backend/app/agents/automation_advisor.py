"""Agent 3 — maps bottlenecks to Microsoft AI and automation solutions."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.prompts.templates import AUTOMATION_ADVISOR_PROMPT
from app.schemas.agent import AutomationPlan


class AutomationAdvisorAgent(BaseAgent[AutomationPlan]):
    template = AUTOMATION_ADVISOR_PROMPT
    output_model = AutomationPlan

    def build_context(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "process_analysis": self.serialize(kwargs["analysis"]),
            "bottlenecks": self.serialize(kwargs["bottlenecks"]),
        }
