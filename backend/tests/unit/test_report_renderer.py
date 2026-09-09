"""Renderer-level guarantees: the LLM cannot put an unbacked figure in the report."""

from __future__ import annotations

from decimal import Decimal

from app.schemas.insight import AnalysisConfidence, ReportNarrative, Roadmap
from app.schemas.roi import ROICalculationInput, ROIResult
from app.services.report_renderer import (
    detect_roi_conflicts,
    render_report,
    sanitise_narrative,
)
from app.services.roi_service import assert_roi_consistency, calculate_roi, roi_values_match

CONFIDENCE = AnalysisConfidence(score=87, level="Medium")


def _roi() -> ROIResult:
    return calculate_roi(
        ROICalculationInput(
            monthly_volume=120,
            minutes_per_case=40,
            hourly_cost=28,
            automation_potential_percentage=55,
        )
    )


def test_llm_supplied_figures_are_flagged_and_overridden() -> None:
    narrative = ReportNarrative(
        executive_summary=(
            "Automation will save 40 hours per month worth $1,120. "
            "The programme is ready to start."
        ),
        roi_interpretation="Annual savings reach 13440.",
    )
    report = render_report(
        process_name="Purchase Approval Process",
        narrative=narrative,
        roi=_roi(),
        confidence=CONFIDENCE,
        recommendations=[],
        quick_wins=[],
        bottlenecks=[],
        roadmap=Roadmap(),
    )
    assert report.roi_overridden is True
    # The authoritative figures — not the model's — appear in the business case.
    assert "| Estimated hours saved per month | 44 hours |" in report.markdown
    assert "| Monthly productivity value | 1232.00 |" in report.markdown
    # ...and the contradicting prose never reaches the reader.
    assert "40 hours" not in report.markdown
    assert "1,120" not in report.markdown
    assert "13440" not in report.markdown
    # Unaffected sentences in the same paragraph survive.
    assert "The programme is ready to start." in report.markdown


def test_sanitiser_keeps_prose_that_only_cites_backed_figures() -> None:
    narrative = ReportNarrative(
        executive_summary="The team recovers 44 hours each month, worth $1232.00.",
        current_state_assessment="Rollout runs over the first 2 waves across 3 teams.",
    )
    cleaned, conflicts = sanitise_narrative(
        narrative, roi=_roi(), confidence=CONFIDENCE, recommendations=[]
    )
    assert conflicts == []
    assert cleaned == narrative


def test_conflict_detector_accepts_backed_figures() -> None:
    conflicts = detect_roi_conflicts(
        narrative_text="The team recovers 44 hours each month, worth 1232.00.",
        roi=_roi(),
        confidence=CONFIDENCE,
        recommendations=[],
    )
    assert conflicts == []


def test_conflict_detector_ignores_incidental_small_numbers() -> None:
    """Plain prose counts must not be mistaken for ROI claims."""
    conflicts = detect_roi_conflicts(
        narrative_text="Two of the 3 approval gates are redundant in the first 2 weeks.",
        roi=_roi(),
        confidence=CONFIDENCE,
        recommendations=[],
    )
    assert conflicts == []


def test_conflict_detector_catches_currency_and_unit_claims() -> None:
    conflicts = detect_roi_conflicts(
        narrative_text="It saves 40 hours and $1,120 monthly, a 70% reduction.",
        roi=_roi(),
        confidence=CONFIDENCE,
        recommendations=[],
    )
    assert set(conflicts) == {"40", "1,120", "70"}


def test_roi_consistency_helper_always_returns_the_source() -> None:
    source = _roi()
    tampered = source.model_copy(update={"estimated_hours_saved": Decimal("40")})
    assert roi_values_match(source, tampered) is False
    assert assert_roi_consistency(
        source=source, candidate=tampered, context="test"
    ).estimated_hours_saved == Decimal("44")


def test_empty_narrative_still_renders_every_section() -> None:
    report = render_report(
        process_name="Purchase Approval Process",
        narrative=ReportNarrative(),
        roi=_roi(),
        confidence=CONFIDENCE,
        recommendations=[],
        quick_wins=[],
        bottlenecks=[],
        roadmap=Roadmap(),
    )
    assert report.roi_overridden is False
    for index in range(1, 12):
        assert f"## {index}. " in report.markdown
    assert "| Estimated hours saved per month | 44 hours |" in report.markdown
