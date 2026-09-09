"""The single source of truth for every ROI number in ProcessPilot AI.

Formulas (no rounding is applied to intermediate values)::

    current_monthly_hours    = monthly_volume * minutes_per_case / 60
    estimated_hours_saved    = current_monthly_hours * automation_potential_percentage / 100
    remaining_monthly_hours  = current_monthly_hours - estimated_hours_saved
    monthly_productivity_value = estimated_hours_saved * hourly_cost
    annual_productivity_value  = monthly_productivity_value * 12

Rounding is applied exactly once, when the :class:`ROIResult` is constructed:
hours to at most 2 dp, currency to exactly 2 dp, percentages to at most 1 dp.
Because the annual value is derived from the *unrounded* monthly value, a
monthly value of 5.8333… correctly yields 70.00 per year rather than 69.96.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.logging import get_correlation_id, get_logger
from app.schemas.roi import (
    MINUTES_PER_HOUR,
    MONTHS_PER_YEAR,
    PERCENT,
    ROICalculationInput,
    ROIRawValues,
    ROIResult,
    round_currency,
    round_hours,
    round_percentage,
    to_decimal,
)

logger = get_logger(__name__)

CALCULATION_METHOD = (
    "current_monthly_hours = monthly_volume x minutes_per_case / 60; "
    "estimated_hours_saved = current_monthly_hours x automation_potential_percentage / 100; "
    "remaining_monthly_hours = current_monthly_hours - estimated_hours_saved; "
    "monthly_productivity_value = estimated_hours_saved x hourly_cost; "
    "annual_productivity_value = monthly_productivity_value x 12. "
    "Computed with decimal arithmetic; rounding is applied only for presentation."
)

BASE_ASSUMPTIONS: tuple[str, ...] = (
    "Volume, handling time and hourly cost are steady-state monthly averages.",
    "Hourly cost is the fully loaded internal cost of the people performing the work.",
    "Savings are expressed as recovered capacity (productivity value), not as headcount "
    "reduction or cash released.",
    "Automation potential reflects the share of current effort that can be removed; the "
    "remaining hours cover exceptions, judgement and oversight.",
    "Implementation, licensing and change-management costs are excluded from the "
    "productivity value figures.",
)

#: ROI score is normalised against this annual saving so the 0-100 scale stays comparable.
ROI_SCORE_REFERENCE_SAVINGS = Decimal(250_000)


def calculate_roi_raw(roi_input: ROICalculationInput) -> ROIRawValues:
    """Pure, unrounded decimal maths. Exposed so tests can assert exact identities."""
    minutes = to_decimal(roi_input.minutes_per_case)
    volume = Decimal(roi_input.monthly_volume)
    hourly_cost = to_decimal(roi_input.hourly_cost)
    percentage = to_decimal(roi_input.automation_potential_percentage)

    current_monthly_hours = (volume * minutes) / MINUTES_PER_HOUR
    estimated_hours_saved = current_monthly_hours * percentage / PERCENT
    remaining_monthly_hours = current_monthly_hours - estimated_hours_saved
    monthly_productivity_value = estimated_hours_saved * hourly_cost
    annual_productivity_value = monthly_productivity_value * MONTHS_PER_YEAR

    return ROIRawValues(
        current_monthly_hours=current_monthly_hours,
        estimated_hours_saved=estimated_hours_saved,
        remaining_monthly_hours=remaining_monthly_hours,
        monthly_productivity_value=monthly_productivity_value,
        annual_productivity_value=annual_productivity_value,
        automation_potential_percentage=percentage,
    )


def _roi_score(raw: ROIRawValues, implementation_cost: Decimal) -> Decimal:
    if implementation_cost > 0:
        score = (
            (raw.annual_productivity_value - implementation_cost) / implementation_cost
        ) * PERCENT
    else:
        score = (raw.annual_productivity_value / ROI_SCORE_REFERENCE_SAVINGS) * PERCENT
    return min(max(score, Decimal(0)), PERCENT)


def calculate_roi(
    roi_input: ROICalculationInput, *, extra_assumptions: list[str] | None = None
) -> ROIResult:
    """Calculate the canonical :class:`ROIResult`.

    This is the *only* place ROI figures are produced. Every consumer — the
    analysis response, persistence, and the executive report — must reuse the
    returned object rather than deriving its own numbers.
    """
    logger.info(
        "roi_calculation_started",
        extra={
            "correlation_id": get_correlation_id(),
            "monthly_volume": roi_input.monthly_volume,
            "minutes_per_case": float(roi_input.minutes_per_case),
            "hourly_cost": float(roi_input.hourly_cost),
            "automation_potential_percentage": float(roi_input.automation_potential_percentage),
        },
    )

    raw = calculate_roi_raw(roi_input)
    score = _roi_score(raw, to_decimal(roi_input.implementation_cost))

    current_hours = round_hours(raw.current_monthly_hours)
    hours_saved = round_hours(raw.estimated_hours_saved)
    monthly_value = round_currency(raw.monthly_productivity_value)
    annual_value = round_currency(raw.annual_productivity_value)

    result = ROIResult(
        current_monthly_hours=current_hours,
        estimated_hours_saved=hours_saved,
        remaining_monthly_hours=round_hours(raw.remaining_monthly_hours),
        monthly_productivity_value=monthly_value,
        annual_productivity_value=annual_value,
        automation_potential_percentage=round_percentage(raw.automation_potential_percentage),
        calculation_method=CALCULATION_METHOD,
        assumptions=[*BASE_ASSUMPTIONS, *(extra_assumptions or [])],
        # Backwards-compatible mirrors of the same validated numbers.
        current_hours=current_hours,
        monthly_savings=monthly_value,
        annual_savings=annual_value,
        roi_score=round_percentage(score),
    )

    logger.info(
        "roi_calculation_completed",
        extra={
            "correlation_id": get_correlation_id(),
            "current_monthly_hours": float(result.current_monthly_hours),
            "estimated_hours_saved": float(result.estimated_hours_saved),
            "remaining_monthly_hours": float(result.remaining_monthly_hours),
            "monthly_productivity_value": float(result.monthly_productivity_value),
            "annual_productivity_value": float(result.annual_productivity_value),
            "automation_potential_percentage": float(result.automation_potential_percentage),
        },
    )
    return result


def zero_roi(reason: str) -> ROIResult:
    """A well-formed, explicitly-zero ROI used when baseline metrics are absent."""
    return ROIResult(
        calculation_method=CALCULATION_METHOD,
        assumptions=[reason, *BASE_ASSUMPTIONS],
    )


def roi_values_match(left: ROIResult, right: ROIResult) -> bool:
    """Strict equality of the values that must never diverge between surfaces."""
    return left.fingerprint() == right.fingerprint()


def assert_roi_consistency(*, source: ROIResult, candidate: ROIResult, context: str) -> ROIResult:
    """Return ``source`` unchanged, logging a warning if ``candidate`` differs.

    The deterministic backend calculation always wins; this function exists so
    a silent divergence can never reach a user-facing surface unnoticed.
    """
    if not roi_values_match(source, candidate):
        logger.warning(
            "roi_consistency_violation",
            extra={
                "correlation_id": get_correlation_id(),
                "context": context,
                "expected": [str(v) for v in source.fingerprint()],
                "received": [str(v) for v in candidate.fingerprint()],
            },
        )
    return source
