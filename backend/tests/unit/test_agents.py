"""Unit tests for the agent layer using the deterministic mock LLM."""

from __future__ import annotations

import pytest

from app.agents import (
    AutomationAdvisorAgent,
    BottleneckDetectionAgent,
    ExecutiveSummaryAgent,
    ProcessAnalyzerAgent,
)
from app.core.exceptions import LLMError
from app.schemas.agent import Effort, ProcessAnalysis, ROIResultSchema, Severity, TokenUsage


async def test_process_analyzer_extracts_structured_model(mock_llm, sample_description) -> None:
    agent = ProcessAnalyzerAgent(mock_llm)
    analysis, usage = await agent.run(
        process_name="Employee Onboarding",
        description=sample_description,
        document_context="",
    )

    assert analysis.process_name == "Employee Onboarding"
    assert analysis.steps
    assert all(step.order == index for index, step in enumerate(analysis.steps, start=1))
    assert analysis.manual_tasks
    assert usage.total_tokens > 0


async def test_bottleneck_agent_returns_normalized_severities(mock_llm) -> None:
    agent = BottleneckDetectionAgent(mock_llm)
    report, _ = await agent.run(analysis=ProcessAnalysis(process_name="Test"))

    assert len(report.bottlenecks) >= 3
    assert all(isinstance(b.severity, Severity) for b in report.bottlenecks)


async def test_automation_advisor_prioritizes_microsoft_stack(mock_llm) -> None:
    agent = AutomationAdvisorAgent(mock_llm)
    plan, _ = await agent.run(analysis=ProcessAnalysis(), bottlenecks=[])

    assert plan.opportunities
    assert all(isinstance(o.implementation_effort, Effort) for o in plan.opportunities)
    technologies = " ".join(o.technology for o in plan.opportunities).lower()
    assert "power automate" in technologies
    assert "azure" in technologies


async def test_executive_summary_contains_required_sections(mock_llm) -> None:
    agent = ExecutiveSummaryAgent(mock_llm)
    report, _ = await agent.run(
        process_name="Employee Onboarding",
        analysis=ProcessAnalysis(process_name="Employee Onboarding"),
        bottlenecks=[],
        opportunities=[],
        roi=ROIResultSchema(),
    )

    for section in (
        "## Current State",
        "## Key Pain Points",
        "## Recommended Solutions",
        "## Expected Benefits",
        "## ROI",
        "## Implementation Roadmap",
    ):
        assert section in report


async def test_agent_raises_llm_error_on_invalid_payload() -> None:
    class BrokenLLM:
        async def complete_json(self, *, system, user, template_name):
            return {"steps": "not-a-list"}, TokenUsage()

        async def complete_text(self, *, system, user, template_name):
            return "", TokenUsage()

    agent = ProcessAnalyzerAgent(BrokenLLM())
    with pytest.raises(LLMError):
        await agent.run(process_name="x", description="y", document_context="")


def test_token_usage_addition_is_component_wise() -> None:
    total = TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15) + TokenUsage(
        prompt_tokens=1, completion_tokens=2, total_tokens=3
    )
    assert (total.prompt_tokens, total.completion_tokens, total.total_tokens) == (11, 7, 18)
