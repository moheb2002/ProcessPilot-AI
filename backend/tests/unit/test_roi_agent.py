"""Unit tests for the deterministic ROI engine.

Currency assertions use ``Decimal`` so no binary-float tolerance is needed.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.agents.roi_agent import ROIAgent, calculate_roi_from_input
from app.schemas.agent import ROIInput
from app.schemas.roi import MONTHS_PER_YEAR, ROICalculationInput
from app.services.roi_service import calculate_roi, calculate_roi_raw


def _input(**kwargs) -> ROICalculationInput:
    return ROICalculationInput(**kwargs)


# --------------------------------------------------------------------------- #
# 1. Fractional hours must not collapse to zero
# --------------------------------------------------------------------------- #
def test_fractional_hours_are_preserved() -> None:
    result = calculate_roi(
        _input(
            monthly_volume=1,
            minutes_per_case=35,
            hourly_cost=20,
            automation_potential_percentage=50,
        )
    )
    assert result.current_monthly_hours == Decimal("0.58")
    assert result.estimated_hours_saved == Decimal("0.29")
    assert result.monthly_productivity_value == Decimal("5.83")
    assert result.annual_productivity_value == Decimal("70.00")
    assert result.estimated_hours_saved > 0


# --------------------------------------------------------------------------- #
# 2. The reference purchase-approval process
# --------------------------------------------------------------------------- #
def test_purchase_process_reference_values() -> None:
    result = calculate_roi(
        _input(
            monthly_volume=120,
            minutes_per_case=40,
            hourly_cost=28,
            automation_potential_percentage=55,
        )
    )
    assert result.current_monthly_hours == Decimal("80")
    assert result.estimated_hours_saved == Decimal("44")
    assert result.remaining_monthly_hours == Decimal("36")
    assert result.monthly_productivity_value == Decimal("1232.00")
    assert result.annual_productivity_value == Decimal("14784.00")
    assert result.automation_potential_percentage == Decimal("55")


# --------------------------------------------------------------------------- #
# 3-5. Boundary conditions
# --------------------------------------------------------------------------- #
def test_zero_hourly_cost_still_reports_hours() -> None:
    result = calculate_roi(
        _input(
            monthly_volume=120,
            minutes_per_case=40,
            hourly_cost=0,
            automation_potential_percentage=55,
        )
    )
    assert result.estimated_hours_saved == Decimal("44")
    assert result.monthly_productivity_value == Decimal("0.00")
    assert result.annual_productivity_value == Decimal("0.00")


def test_zero_percent_reduction_saves_nothing() -> None:
    result = calculate_roi(
        _input(
            monthly_volume=120,
            minutes_per_case=40,
            hourly_cost=28,
            automation_potential_percentage=0,
        )
    )
    assert result.estimated_hours_saved == Decimal("0")
    assert result.remaining_monthly_hours == result.current_monthly_hours
    assert result.monthly_productivity_value == Decimal("0.00")


def test_full_reduction_removes_all_effort() -> None:
    result = calculate_roi(
        _input(
            monthly_volume=120,
            minutes_per_case=40,
            hourly_cost=28,
            automation_potential_percentage=100,
        )
    )
    assert result.estimated_hours_saved == Decimal("80")
    assert result.remaining_monthly_hours == Decimal("0")
    assert result.monthly_productivity_value == Decimal("2240.00")
    assert result.annual_productivity_value == Decimal("26880.00")


# --------------------------------------------------------------------------- #
# 6-7. Validation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "payload",
    [
        {"monthly_volume": 0, "minutes_per_case": 40, "hourly_cost": 28,
         "automation_potential_percentage": 55},
        {"monthly_volume": -5, "minutes_per_case": 40, "hourly_cost": 28,
         "automation_potential_percentage": 55},
        {"monthly_volume": 10, "minutes_per_case": 0, "hourly_cost": 28,
         "automation_potential_percentage": 55},
        {"monthly_volume": 10, "minutes_per_case": -1, "hourly_cost": 28,
         "automation_potential_percentage": 55},
        {"monthly_volume": 10, "minutes_per_case": 40, "hourly_cost": -1,
         "automation_potential_percentage": 55},
    ],
)
def test_invalid_negative_values_are_rejected(payload: dict) -> None:
    with pytest.raises(PydanticValidationError):
        ROICalculationInput(**payload)


@pytest.mark.parametrize("percentage", [100.1, 120, 1000, -1])
def test_automation_percentage_must_be_between_zero_and_one_hundred(percentage: float) -> None:
    with pytest.raises(PydanticValidationError):
        ROICalculationInput(
            monthly_volume=10,
            minutes_per_case=40,
            hourly_cost=28,
            automation_potential_percentage=percentage,
        )


# --------------------------------------------------------------------------- #
# 8. Large volumes
# --------------------------------------------------------------------------- #
def test_large_monthly_volume_is_exact() -> None:
    result = calculate_roi(
        _input(
            monthly_volume=1_000_000,
            minutes_per_case=6,
            hourly_cost=30,
            automation_potential_percentage=60,
        )
    )
    assert result.current_monthly_hours == Decimal("100000")
    assert result.estimated_hours_saved == Decimal("60000")
    assert result.monthly_productivity_value == Decimal("1800000.00")
    assert result.annual_productivity_value == Decimal("21600000.00")


# --------------------------------------------------------------------------- #
# Identity checks
# --------------------------------------------------------------------------- #
def test_monthly_value_equals_hours_saved_times_hourly_cost() -> None:
    raw = calculate_roi_raw(
        _input(
            monthly_volume=137,
            minutes_per_case=23,
            hourly_cost="41.5",
            automation_potential_percentage="37.5",
        )
    )
    assert raw.monthly_productivity_value == raw.estimated_hours_saved * Decimal("41.5")


def test_annual_value_equals_monthly_value_times_twelve() -> None:
    raw = calculate_roi_raw(
        _input(
            monthly_volume=137,
            minutes_per_case=23,
            hourly_cost="41.5",
            automation_potential_percentage="37.5",
        )
    )
    assert raw.annual_productivity_value == raw.monthly_productivity_value * MONTHS_PER_YEAR


def test_hours_split_between_saved_and_remaining() -> None:
    raw = calculate_roi_raw(
        _input(
            monthly_volume=120,
            minutes_per_case=40,
            hourly_cost=28,
            automation_potential_percentage=55,
        )
    )
    assert raw.estimated_hours_saved + raw.remaining_monthly_hours == raw.current_monthly_hours


def test_legacy_aliases_mirror_canonical_values() -> None:
    result = calculate_roi(
        _input(
            monthly_volume=120,
            minutes_per_case=40,
            hourly_cost=28,
            automation_potential_percentage=55,
        )
    )
    assert result.current_hours == result.current_monthly_hours
    assert result.monthly_savings == result.monthly_productivity_value
    assert result.annual_savings == result.annual_productivity_value


def test_legacy_automation_rate_is_converted_to_percentage() -> None:
    payload = ROICalculationInput.model_validate(
        {
            "monthly_volume": 120,
            "minutes_per_transaction": 40,
            "employee_hourly_rate": 28,
            "automation_rate": 0.55,
        }
    )
    assert payload.automation_potential_percentage == Decimal("55.00")
    assert calculate_roi(payload).estimated_hours_saved == Decimal("44")


def test_missing_baseline_metrics_yield_explicit_zero_roi() -> None:
    result = calculate_roi_from_input(ROIInput(), Decimal(50))
    assert result.current_monthly_hours == Decimal(0)
    assert result.annual_productivity_value == Decimal("0.00")
    assert result.assumptions  # the reason is recorded, not silently dropped


# --------------------------------------------------------------------------- #
# Agent behaviour
# --------------------------------------------------------------------------- #
async def test_roi_agent_uses_llm_estimated_automation_potential(mock_llm) -> None:
    agent = ROIAgent(mock_llm)
    result, usage = await agent.run(
        roi_input=ROIInput(monthly_volume=100, minutes_per_case=60, hourly_cost=100)
    )
    # Mock client returns automation_rate = 0.55 -> 100h * 55% * 100 = 5_500
    assert result.roi.automation_potential_percentage == Decimal("55")
    assert result.roi.estimated_hours_saved == Decimal("55")
    assert result.roi.monthly_productivity_value == Decimal("5500.00")
    assert result.automation_potential.percentage == result.roi.automation_potential_percentage
    assert usage.total_tokens > 0


async def test_roi_agent_skips_llm_when_metrics_are_missing(mock_llm) -> None:
    agent = ROIAgent(mock_llm)
    result, usage = await agent.run(roi_input=ROIInput())
    assert usage.total_tokens == 0
    assert result.roi.monthly_productivity_value == Decimal("0.00")


async def test_caller_supplied_percentage_bypasses_the_llm(mock_llm) -> None:
    agent = ROIAgent(mock_llm)
    result, usage = await agent.run(
        roi_input=ROIInput(
            monthly_volume=120,
            minutes_per_case=40,
            hourly_cost=28,
            automation_potential_percentage=55,
        )
    )
    assert usage.total_tokens == 0
    assert result.roi.estimated_hours_saved == Decimal("44")


async def test_explicit_zero_percentage_is_not_treated_as_absent(mock_llm) -> None:
    """A deliberate 0% must be honoured, not replaced by an estimate or the default."""
    agent = ROIAgent(mock_llm)
    result, usage = await agent.run(
        roi_input=ROIInput.model_validate(
            {
                "monthly_volume": 120,
                "minutes_per_case": 40,
                "hourly_cost": 28,
                "automation_potential_percentage": 0,
                "automation_rate": 0.55,
            }
        )
    )
    assert usage.total_tokens == 0
    assert result.roi.automation_potential_percentage == Decimal(0)
    assert result.roi.estimated_hours_saved == Decimal(0)


async def test_agent_reuses_one_calculation_input(mock_llm) -> None:
    """The persisted inputs must reproduce the returned ROI exactly."""
    agent = ROIAgent(mock_llm)
    result, _ = await agent.run(
        roi_input=ROIInput(monthly_volume=120, minutes_per_case=40, hourly_cost=28)
    )
    assert result.calculation_input is not None
    assert (
        result.calculation_input.automation_potential_percentage
        == result.roi.automation_potential_percentage
    )
    assert calculate_roi(result.calculation_input).fingerprint() == result.roi.fingerprint()
