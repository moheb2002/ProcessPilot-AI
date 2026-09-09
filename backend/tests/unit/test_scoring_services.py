"""Unit tests for the deterministic scoring services."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from app.core.exceptions import ValidationError as AppValidationError
from app.core.scoring_config import QUICK_WIN_RULES, RECOMMENDATION_SCORING, SAVINGS_ALLOCATION
from app.schemas.agent import AutomationOpportunity, Bottleneck, ProcessAnalysis, ProcessStep
from app.schemas.insight import (
    BusinessImpact,
    ConfidenceLevel,
    Frequency,
    ImplementationEffort,
    RiskReduction,
)
from app.schemas.roi import ROICalculationInput
from app.services.confidence_service import calculate_confidence
from app.services.recommendation_service import (
    build_recommendations,
    frequency_for_volume,
    score_recommendation,
    select_quick_wins,
    validate_savings_allocation,
)
from app.services.roi_service import calculate_roi

ROI_INPUT = ROICalculationInput(
    monthly_volume=120,
    minutes_per_case=40,
    hourly_cost=28,
    automation_potential_percentage=55,
)
ROI = calculate_roi(ROI_INPUT)

BOTTLENECKS = [
    Bottleneck(
        title="Manual data re-entry across systems",
        severity="critical",
        impact="Adds cycle time and introduces data-quality errors.",
        recommendation="Replace re-keying with an automated flow.",
    ),
    Bottleneck(
        title="Sequential approval chain",
        severity="high",
        impact="Approvals sit idle in inboxes.",
        recommendation="Move approvals into Teams.",
    ),
    Bottleneck(
        title="Unstructured email hand-offs",
        severity="medium",
        impact="No SLA visibility.",
        recommendation="Introduce a tracked intake queue.",
    ),
]

OPPORTUNITIES = [
    AutomationOpportunity(
        solution="Automated approval routing replacing the sequential approval chain",
        technology="Power Automate + Microsoft Teams",
        business_value="Cuts approval wait time.",
        implementation_effort="low",
    ),
    AutomationOpportunity(
        solution="Eliminate manual re-entry between systems",
        technology="Power Automate",
        business_value="Removes re-keying of the same data.",
        implementation_effort="medium",
    ),
    AutomationOpportunity(
        solution="Grounded assistant over policies",
        technology="Azure OpenAI + Azure AI Search",
        business_value="Answers policy questions instantly.",
        implementation_effort="high",
    ),
]


def _analysis(steps: int = 10, actors: int = 3, systems: int = 2) -> ProcessAnalysis:
    return ProcessAnalysis(
        process_name="Purchase Approval Process",
        actors=[f"Actor {i}" for i in range(actors)],
        systems=[f"System {i}" for i in range(systems)],
        steps=[
            ProcessStep(order=i, name=f"Step {i}", is_manual=i % 2 == 0, estimated_minutes=5)
            for i in range(1, steps + 1)
        ],
        approvals=["Manager approval"],
        manual_tasks=["Re-key invoice data"],
    )


# --------------------------------------------------------------------------- #
# Confidence
# --------------------------------------------------------------------------- #
def test_confidence_score_stays_within_bounds() -> None:
    for description in ("", "short", "x" * 5_000):
        confidence = calculate_confidence(
            description=description,
            analysis=_analysis(),
            bottlenecks=BOTTLENECKS,
            roi_input=ROI_INPUT,
        )
        assert 0 <= confidence.score <= 100


def test_rich_input_scores_high_and_sparse_input_scores_low() -> None:
    rich = calculate_confidence(
        description="x" * 1_200,
        analysis=_analysis(),
        bottlenecks=BOTTLENECKS,
        roi_input=ROI_INPUT,
    )
    sparse = calculate_confidence(
        description="A short note.",
        analysis=_analysis(steps=2, actors=0, systems=0),
        bottlenecks=[],
        roi_input=None,
    )
    assert rich.score > sparse.score
    assert rich.level is ConfidenceLevel.HIGH
    assert sparse.level is ConfidenceLevel.LOW
    assert sparse.missing_information


def test_confidence_level_thresholds() -> None:
    medium = calculate_confidence(
        description="x" * 300,
        analysis=_analysis(steps=5),
        bottlenecks=BOTTLENECKS[:1],
        roi_input=ROI_INPUT,
    )
    assert 70 <= medium.score < 90
    assert medium.level is ConfidenceLevel.MEDIUM


def test_missing_hourly_cost_is_reported_as_a_gap() -> None:
    confidence = calculate_confidence(
        description="x" * 1_200,
        analysis=_analysis(),
        bottlenecks=BOTTLENECKS,
        roi_input=ROICalculationInput(
            monthly_volume=120,
            minutes_per_case=40,
            hourly_cost=0,
            automation_potential_percentage=55,
        ),
    )
    assert any("hourly cost" in gap for gap in confidence.missing_information)


# --------------------------------------------------------------------------- #
# Recommendation scoring
# --------------------------------------------------------------------------- #
def test_score_formula_matches_the_configured_weights() -> None:
    score, explanation = score_recommendation(
        business_impact=BusinessImpact.CRITICAL,
        implementation_effort=ImplementationEffort.LOW,
        frequency=Frequency.VERY_HIGH,
        risk_reduction=RiskReduction.CRITICAL,
    )
    assert score == 100.0  # (4 + 4 + 4) / 1 == max raw score
    assert "normalised" in explanation

    worst, _ = score_recommendation(
        business_impact=BusinessImpact.LOW,
        implementation_effort=ImplementationEffort.HIGH,
        frequency=Frequency.LOW,
        risk_reduction=RiskReduction.LOW,
    )
    assert worst == 0.0
    assert RECOMMENDATION_SCORING.max_raw_score == 12.0


@pytest.mark.parametrize(
    ("volume", "expected"),
    [
        (5_000, Frequency.VERY_HIGH),
        (500, Frequency.HIGH),
        (50, Frequency.MEDIUM),
        (5, Frequency.LOW),
    ],
)
def test_frequency_bands(volume: int, expected: Frequency) -> None:
    assert frequency_for_volume(volume) is expected


def test_recommendations_are_sorted_by_score_descending() -> None:
    recommendations = build_recommendations(
        opportunities=OPPORTUNITIES,
        bottlenecks=BOTTLENECKS,
        roi=ROI,
        monthly_volume=120,
        hourly_cost=Decimal(28),
    )
    scores = [r.recommendation_score for r in recommendations]
    assert scores == sorted(scores, reverse=True)
    assert all(r.id.startswith("REC-") for r in recommendations)
    assert all(r.score_explanation for r in recommendations)


def test_recommendation_hours_never_exceed_the_overall_roi() -> None:
    recommendations = build_recommendations(
        opportunities=OPPORTUNITIES,
        bottlenecks=BOTTLENECKS,
        roi=ROI,
        monthly_volume=120,
        hourly_cost=Decimal(28),
    )
    total = sum(
        (Decimal(r.estimated_hours_saved_per_month) for r in recommendations), Decimal(0)
    )
    assert total <= Decimal(ROI.estimated_hours_saved)
    validate_savings_allocation(recommendations=recommendations, roi=ROI)


def test_zero_roi_allocates_zero_hours() -> None:
    zero = calculate_roi(
        ROICalculationInput(
            monthly_volume=120,
            minutes_per_case=40,
            hourly_cost=28,
            automation_potential_percentage=0,
        )
    )
    recommendations = build_recommendations(
        opportunities=OPPORTUNITIES,
        bottlenecks=BOTTLENECKS,
        roi=zero,
        monthly_volume=120,
        hourly_cost=Decimal(28),
    )
    assert all(r.estimated_hours_saved_per_month == Decimal(0) for r in recommendations)


@pytest.mark.parametrize("recommendation_count", [1, 2, 3, 6, 12])
def test_rounded_allocation_never_drifts_above_the_total(recommendation_count: int) -> None:
    """Rounding each share to 2 dp must not push the sum past the ROI ceiling."""
    roi = calculate_roi(
        ROICalculationInput(
            monthly_volume=7,
            minutes_per_case=13,
            hourly_cost="17.37",
            automation_potential_percentage="37.5",
        )
    )
    recommendations = build_recommendations(
        opportunities=OPPORTUNITIES * recommendation_count,
        bottlenecks=BOTTLENECKS,
        roi=roi,
        monthly_volume=7,
        hourly_cost=Decimal("17.37"),
    )
    total = sum(
        (Decimal(r.estimated_hours_saved_per_month) for r in recommendations), Decimal(0)
    )
    assert total <= Decimal(roi.estimated_hours_saved)


def test_strict_allocation_raises_on_a_manual_over_allocation() -> None:
    inflated = build_recommendations(
        opportunities=OPPORTUNITIES,
        bottlenecks=BOTTLENECKS,
        roi=ROI,
        monthly_volume=120,
        hourly_cost=Decimal(28),
    )
    inflated = [
        r.model_copy(update={"estimated_hours_saved_per_month": Decimal(100)}) for r in inflated
    ]
    with pytest.raises(AppValidationError):
        validate_savings_allocation(
            recommendations=inflated,
            roi=ROI,
            allocation=replace(SAVINGS_ALLOCATION, strict=True),
        )


# --------------------------------------------------------------------------- #
# Quick Wins
# --------------------------------------------------------------------------- #
def test_quick_wins_are_capped_at_three_and_satisfy_the_rules() -> None:
    recommendations = build_recommendations(
        opportunities=OPPORTUNITIES * 3,
        bottlenecks=BOTTLENECKS,
        roi=ROI,
        monthly_volume=120,
        hourly_cost=Decimal(28),
    )
    quick_wins = select_quick_wins(recommendations)

    assert len(quick_wins) <= QUICK_WIN_RULES.max_results
    by_id = {r.id: r for r in recommendations}
    for win in quick_wins:
        source = by_id[win.source_recommendation_id]
        assert source.implementation_effort.value.casefold() in QUICK_WIN_RULES.allowed_efforts
        assert source.business_impact.value.casefold() in QUICK_WIN_RULES.allowed_impacts
        assert source.implementation_timeframe_days <= QUICK_WIN_RULES.max_timeframe_days
        assert len(source.dependencies) <= QUICK_WIN_RULES.max_dependencies


def test_not_every_recommendation_becomes_a_quick_win() -> None:
    low_value = [
        AutomationOpportunity(
            solution="Long-running platform migration",
            technology="Azure OpenAI",
            business_value="Strategic modernisation.",
            implementation_effort="high",
        )
    ]
    recommendations = build_recommendations(
        opportunities=low_value,
        bottlenecks=[],
        roi=ROI,
        monthly_volume=5,
        hourly_cost=Decimal(28),
    )
    assert select_quick_wins(recommendations) == []
