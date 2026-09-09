"""Unit tests for the agent layer using the deterministic mock LLM."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.agents import (
    AutomationAdvisorAgent,
    BottleneckDetectionAgent,
    ExecutiveSummaryAgent,
    ProcessAnalyzerAgent,
)
from app.core.exceptions import LLMError
from app.schemas.agent import (
    AutomationOpportunity,
    Bottleneck,
    Effort,
    ProcessAnalysis,
    ProcessStep,
    ROIResult,
    Severity,
    TokenUsage,
)
from app.schemas.insight import AnalysisConfidence, ReportNarrative


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
    report, _ = await agent.run(
        analysis=ProcessAnalysis(
            process_name="Test",
            steps=[ProcessStep(order=1, name="Review request")],
        )
    )

    assert len(report.bottlenecks) >= 3
    assert all(isinstance(b.severity, Severity) for b in report.bottlenecks)


async def test_automation_advisor_prioritizes_microsoft_stack(mock_llm) -> None:
    agent = AutomationAdvisorAgent(mock_llm)
    plan, _ = await agent.run(
        analysis=ProcessAnalysis(steps=[ProcessStep(order=1, name="Review request")]),
        bottlenecks=[],
    )

    assert plan.opportunities
    assert all(isinstance(o.implementation_effort, Effort) for o in plan.opportunities)
    technologies = " ".join(o.technology for o in plan.opportunities).lower()
    assert "power automate" in technologies
    assert "azure" in technologies


async def test_executive_summary_returns_prose_without_numbers(mock_llm) -> None:
    agent = ExecutiveSummaryAgent(mock_llm)
    narrative, usage = await agent.run(
        process_name="Employee Onboarding",
        analysis=ProcessAnalysis(
            process_name="Employee Onboarding",
            steps=[ProcessStep(order=1, name="Review request")],
        ),
        bottlenecks=[],
        recommendations=[],
        quick_wins=[],
        confidence=AnalysisConfidence(score=80, level="Medium"),
        roi=ROIResult(),
    )

    assert isinstance(narrative, ReportNarrative)
    assert narrative.executive_summary
    assert narrative.key_pain_points
    assert usage.total_tokens > 0


async def test_executive_summary_survives_a_malformed_payload() -> None:
    class BrokenLLM:
        async def complete_json(self, *, system, user, template_name):
            return {"key_pain_points": "not-a-list"}, TokenUsage(total_tokens=1)

        async def complete_text(self, *, system, user, template_name):
            return "", TokenUsage()

    narrative, _ = await ExecutiveSummaryAgent(BrokenLLM()).run(
        process_name="X",
        analysis=ProcessAnalysis(steps=[ProcessStep(order=1, name="Step")]),
        bottlenecks=[],
        recommendations=[],
        quick_wins=[],
        confidence=AnalysisConfidence(),
        roi=ROIResult(),
    )
    assert narrative == ReportNarrative()


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


def test_process_analysis_rejects_missing_or_nonsequential_steps() -> None:
    with pytest.raises(PydanticValidationError):
        ProcessAnalysis.model_validate({})

    with pytest.raises(PydanticValidationError):
        ProcessAnalysis(steps=[ProcessStep(order=2, name="Review request")])


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (Bottleneck, {"title": "Manual handoff", "impact": "", "recommendation": "Fix"}),
        (
            AutomationOpportunity,
            {"solution": "Automate intake", "technology": "", "business_value": "Faster"},
        ),
    ],
)
def test_agent_outputs_require_evidence_bearing_fields(model, payload) -> None:
    with pytest.raises(PydanticValidationError):
        model.model_validate(payload)
