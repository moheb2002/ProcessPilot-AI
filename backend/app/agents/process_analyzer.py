"""Agent 1 — decomposes a narrative description into a structured process model."""

from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.prompts.templates import PROCESS_ANALYSIS_PROMPT
from app.schemas.agent import ProcessAnalysis

MAX_DOCUMENT_CONTEXT_CHARS = 12_000


class ProcessAnalyzerAgent(BaseAgent[ProcessAnalysis]):
    template = PROCESS_ANALYSIS_PROMPT
    output_model = ProcessAnalysis

    def build_context(self, **kwargs: Any) -> dict[str, Any]:
        document_context: str = kwargs.get("document_context") or ""
        return {
            "process_name": kwargs["process_name"],
            "description": kwargs["description"],
            "document_context": document_context[:MAX_DOCUMENT_CONTEXT_CHARS] or "(none provided)",
        }
