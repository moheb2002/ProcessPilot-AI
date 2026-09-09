"""Agent 2 — identifies bottlenecks in a structured process model."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.prompts.templates import BOTTLENECK_DETECTION_PROMPT
from app.schemas.agent import BottleneckReport


class BottleneckDetectionAgent(BaseAgent[BottleneckReport]):
    template = BOTTLENECK_DETECTION_PROMPT
    output_model = BottleneckReport

    def build_context(self, **kwargs: Any) -> dict[str, Any]:
        return {"process_analysis": self.serialize(kwargs["analysis"])}
