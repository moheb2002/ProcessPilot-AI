"""Unit tests for the deterministic ROI calculation."""

from __future__ import annotations

from app.agents.roi_agent import ROIAgent, calculate_roi
from app.schemas.agent import ROIInput


def test_current_hours_converts_minutes_to_hours() -> None:
    result = calculate_roi(
        ROIInput(monthly_volume=100, minutes_per_transaction=30, employee_hourly_rate=50)
    )
    assert result.current_hours == 50.0


def test_savings_scale_with_automation_rate() -> None:
    result = calculate_roi(
        ROIInput(
            monthly_volume=200,
            minutes_per_transaction=60,
            employee_hourly_rate=40,
            automation_rate=0.5,
        )
    )
    assert result.estimated_hours_saved == 100.0
    assert result.monthly_savings == 4000.0
    assert result.annual_savings == 48000.0


def test_roi_score_uses_implementation_cost_when_provided() -> None:
    result = calculate_roi(
        ROIInput(
            monthly_volume=100,
            minutes_per_transaction=60,
            employee_hourly_rate=50,
            automation_rate=1.0,
            implementation_cost=30000,
        )
    )
    # annual savings = 100 * 1h * 50 * 12 = 60_000 -> (60000-30000)/30000 * 100 = 100
    assert result.annual_savings == 60000.0
    assert result.roi_score == 100.0


def test_roi_score_is_clamped_to_zero_hundred() -> None:
    result = calculate_roi(
        ROIInput(
            monthly_volume=1,
            minutes_per_transaction=1,
            employee_hourly_rate=1,
            implementation_cost=1_000_000,
        )
    )
    assert result.roi_score == 0.0


def test_zero_volume_yields_zero_savings() -> None:
    result = calculate_roi(ROIInput())
    assert result.current_hours == 0
    assert result.annual_savings == 0
    assert result.roi_score == 0


async def test_roi_agent_uses_llm_estimated_automation_rate(mock_llm) -> None:
    agent = ROIAgent(mock_llm)
    result, usage = await agent.run(
        roi_input=ROIInput(
            monthly_volume=100, minutes_per_transaction=60, employee_hourly_rate=100
        )
    )
    # Mock client returns automation_rate = 0.55 -> 100h * 0.55 * 100 = 5_500
    assert result.estimated_hours_saved == 55.0
    assert result.monthly_savings == 5500.0
    assert usage.total_tokens > 0


async def test_roi_agent_skips_llm_when_volume_is_zero(mock_llm) -> None:
    agent = ROIAgent(mock_llm)
    result, usage = await agent.run(roi_input=ROIInput())
    assert usage.total_tokens == 0
    assert result.monthly_savings == 0
