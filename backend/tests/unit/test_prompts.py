"""Quality guardrails for versioned agent prompts."""

from app.prompts.templates import (
    AUTOMATION_ADVISOR_PROMPT,
    BOTTLENECK_DETECTION_PROMPT,
    PROCESS_ANALYSIS_PROMPT,
)


def test_analysis_prompt_does_not_invite_invented_durations() -> None:
    assert "Do not infer durations" in PROCESS_ANALYSIS_PROMPT.user
    assert PROCESS_ANALYSIS_PROMPT.version == "1.1.0"


def test_downstream_prompts_prioritize_evidence_over_forced_counts() -> None:
    assert "Return an empty list" in BOTTLENECK_DETECTION_PROMPT.user
    assert "Never invent quantities" in BOTTLENECK_DETECTION_PROMPT.user
    assert "Return an empty list" in AUTOMATION_ADVISOR_PROMPT.user
    assert "Do not assume APIs" in AUTOMATION_ADVISOR_PROMPT.user