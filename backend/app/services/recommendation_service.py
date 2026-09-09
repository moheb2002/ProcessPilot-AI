"""Deterministic recommendation scoring, savings allocation and Quick Win selection.

The LLM proposes *what* to build; this module decides how valuable it is, how
the overall automation savings are apportioned across proposals, and which
proposals qualify as Quick Wins. None of those decisions are delegated to a
model, so results are reproducible and auditable.
"""

from __future__ import annotations

from decimal import Decimal

from app.core.exceptions import ValidationError
from app.core.logging import get_correlation_id, get_logger
from app.core.scoring_config import (
    QUICK_WIN_RULES,
    RECOMMENDATION_SCORING,
    SAVINGS_ALLOCATION,
    QuickWinRules,
    RecommendationScoringConfig,
    SavingsAllocationConfig,
)
from app.schemas.agent import AutomationOpportunity, Bottleneck, Severity
from app.schemas.insight import (
    BusinessImpact,
    Frequency,
    ImplementationComplexity,
    ImplementationEffort,
    Priority,
    QuickWin,
    RecommendationDetail,
    RiskReduction,
)
from app.schemas.roi import MONTHS_PER_YEAR, ROIResult, round_currency, round_hours, to_decimal

logger = get_logger(__name__)

_SEVERITY_TO_IMPACT: dict[Severity, BusinessImpact] = {
    Severity.CRITICAL: BusinessImpact.CRITICAL,
    Severity.HIGH: BusinessImpact.HIGH,
    Severity.MEDIUM: BusinessImpact.MEDIUM,
    Severity.LOW: BusinessImpact.LOW,
}
_SEVERITY_TO_RISK: dict[Severity, RiskReduction] = {
    Severity.CRITICAL: RiskReduction.CRITICAL,
    Severity.HIGH: RiskReduction.HIGH,
    Severity.MEDIUM: RiskReduction.MEDIUM,
    Severity.LOW: RiskReduction.LOW,
}
_EFFORT_MAP: dict[str, ImplementationEffort] = {
    "low": ImplementationEffort.LOW,
    "medium": ImplementationEffort.MEDIUM,
    "high": ImplementationEffort.HIGH,
}


def bottleneck_id(index: int) -> str:
    return f"BN-{index + 1}"


def recommendation_id(index: int) -> str:
    return f"REC-{index + 1}"


def frequency_for_volume(monthly_volume: int) -> Frequency:
    """Transaction frequency band derived from the supplied monthly volume."""
    if monthly_volume >= 1_000:
        return Frequency.VERY_HIGH
    if monthly_volume >= 200:
        return Frequency.HIGH
    if monthly_volume >= 20:
        return Frequency.MEDIUM
    return Frequency.LOW


def _link_bottlenecks(
    opportunity: AutomationOpportunity, bottlenecks: list[Bottleneck]
) -> list[tuple[str, Bottleneck]]:
    """Match an opportunity to bottlenecks by significant shared vocabulary."""
    haystack = f"{opportunity.solution} {opportunity.business_value}".casefold()
    matches: list[tuple[str, Bottleneck]] = []
    for index, bottleneck in enumerate(bottlenecks):
        keywords = {
            word
            for word in bottleneck.title.casefold().replace("-", " ").split()
            if len(word) > 4
        }
        if keywords and any(word in haystack for word in keywords):
            matches.append((bottleneck_id(index), bottleneck))
    return matches


def score_recommendation(
    *,
    business_impact: BusinessImpact,
    implementation_effort: ImplementationEffort,
    frequency: Frequency,
    risk_reduction: RiskReduction,
    config: RecommendationScoringConfig = RECOMMENDATION_SCORING,
) -> tuple[float, str]:
    """``(impact + frequency + risk) / effort`` normalised to a 0-100 scale."""
    impact_score = config.business_impact[business_impact.value.casefold()]
    effort_score = config.implementation_effort[implementation_effort.value.casefold()]
    frequency_score = config.frequency[frequency.value.casefold()]
    risk_score = config.risk_reduction[risk_reduction.value.casefold()]

    raw = (impact_score + frequency_score + risk_score) / effort_score
    span = config.max_raw_score - config.min_raw_score
    normalised = ((raw - config.min_raw_score) / span) * 100 if span else 0.0
    normalised = round(min(max(normalised, 0.0), 100.0), 1)

    explanation = (
        f"(business impact {impact_score} + frequency {frequency_score} + "
        f"risk reduction {risk_score}) / implementation effort {effort_score} = "
        f"{raw:.2f} raw, normalised to {normalised}/100 against a best-case raw score of "
        f"{config.max_raw_score:g}."
    )
    return normalised, explanation


def _priority_for(score: float, config: RecommendationScoringConfig) -> Priority:
    if score >= config.priority_critical_min:
        return Priority.CRITICAL
    if score >= config.priority_high_min:
        return Priority.HIGH
    if score >= config.priority_medium_min:
        return Priority.MEDIUM
    return Priority.LOW


def build_recommendations(
    *,
    opportunities: list[AutomationOpportunity],
    bottlenecks: list[Bottleneck],
    roi: ROIResult,
    monthly_volume: int,
    hourly_cost: Decimal,
    config: RecommendationScoringConfig = RECOMMENDATION_SCORING,
    allocation: SavingsAllocationConfig = SAVINGS_ALLOCATION,
) -> list[RecommendationDetail]:
    """Score, sort and value every opportunity against the validated ROI total."""
    frequency = frequency_for_volume(monthly_volume)
    drafts: list[RecommendationDetail] = []

    for index, opportunity in enumerate(opportunities):
        linked = _link_bottlenecks(opportunity, bottlenecks)
        severities = [b.severity for _, b in linked]
        top_severity = _highest_severity(severities)
        business_impact = _SEVERITY_TO_IMPACT[top_severity]
        risk_reduction = _SEVERITY_TO_RISK[top_severity]
        effort = _EFFORT_MAP.get(str(opportunity.implementation_effort), ImplementationEffort.MEDIUM)

        score, explanation = score_recommendation(
            business_impact=business_impact,
            implementation_effort=effort,
            frequency=frequency,
            risk_reduction=risk_reduction,
            config=config,
        )
        technologies = [
            part.strip()
            for part in opportunity.technology.replace(" and ", "+").split("+")
            if part.strip()
        ]
        drafts.append(
            RecommendationDetail(
                id=recommendation_id(index),
                title=opportunity.solution,
                description=opportunity.business_value,
                related_bottleneck_ids=[bid for bid, _ in linked],
                priority=_priority_for(score, config),
                business_impact=business_impact,
                implementation_effort=effort,
                implementation_complexity=ImplementationComplexity(effort.value),
                frequency=frequency,
                risk_reduction=risk_reduction,
                recommended_technologies=technologies,
                expected_benefits=[b.impact for _, b in linked] or [opportunity.business_value],
                dependencies=_dependencies_for(effort),
                implementation_notes=opportunity.business_value,
                implementation_timeframe_days=QUICK_WIN_RULES.timeframe_by_effort[
                    effort.value.casefold()
                ],
                recommendation_score=score,
                score_explanation=explanation,
            )
        )

    drafts.sort(key=lambda r: (-r.recommendation_score, r.id))
    allocated = allocate_savings(
        recommendations=drafts, roi=roi, hourly_cost=hourly_cost, allocation=allocation
    )

    logger.info(
        "recommendations_scored",
        extra={
            "correlation_id": get_correlation_id(),
            "count": len(allocated),
            "top_score": allocated[0].recommendation_score if allocated else 0.0,
        },
    )
    return allocated


def _highest_severity(severities: list[Severity]) -> Severity:
    order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
    if not severities:
        return Severity.MEDIUM
    return max(severities, key=order.index)


def _dependencies_for(effort: ImplementationEffort) -> list[str]:
    if effort is ImplementationEffort.LOW:
        return ["Power Platform environment and standard connector licensing."]
    if effort is ImplementationEffort.MEDIUM:
        return [
            "Power Platform environment and standard connector licensing.",
            "Access to the system of record (API or supported connector).",
        ]
    return [
        "Azure subscription with the required AI services enabled.",
        "Access to the system of record (API or supported connector).",
        "Data owner sign-off and a representative document/data sample.",
    ]


def allocate_savings(
    *,
    recommendations: list[RecommendationDetail],
    roi: ROIResult,
    hourly_cost: Decimal,
    allocation: SavingsAllocationConfig = SAVINGS_ALLOCATION,
) -> list[RecommendationDetail]:
    """Apportion the validated total hours saved across recommendations.

    Hours are distributed in proportion to ``recommendation_score`` so the sum
    of the per-recommendation estimates equals — and can never exceed — the
    overall ``roi.estimated_hours_saved``. This deliberately avoids double
    counting effort that several recommendations address jointly.
    """
    if not recommendations:
        return []

    total_hours = to_decimal(roi.estimated_hours_saved)
    if total_hours <= 0:
        return [
            r.model_copy(
                update={
                    "estimated_hours_saved_per_month": Decimal(0),
                    "estimated_monthly_value": Decimal("0.00"),
                    "estimated_annual_value": Decimal("0.00"),
                }
            )
            for r in recommendations
        ]

    weights = [to_decimal(max(r.recommendation_score, 1.0)) for r in recommendations]
    weight_total = sum(weights, Decimal(0))
    rate = to_decimal(hourly_cost)
    ceiling = round_hours(total_hours)

    # Round each share first, then give the last recommendation whatever is left, so the
    # rounded shares sum to the ceiling exactly instead of drifting above it.
    shares: list[Decimal] = []
    running = Decimal(0)
    for position, weight in enumerate(weights):
        if position == len(weights) - 1:
            share = max(ceiling - running, Decimal(0))
        else:
            share = round_hours(total_hours * weight / weight_total)
            share = min(share, max(ceiling - running, Decimal(0)))
        shares.append(share)
        running += share

    allocated: list[RecommendationDetail] = []
    for recommendation, share in zip(recommendations, shares, strict=True):
        monthly_value = share * rate
        allocated.append(
            recommendation.model_copy(
                update={
                    "estimated_hours_saved_per_month": share,
                    "estimated_monthly_value": round_currency(monthly_value),
                    "estimated_annual_value": round_currency(monthly_value * MONTHS_PER_YEAR),
                }
            )
        )

    validate_savings_allocation(recommendations=allocated, roi=roi, allocation=allocation)
    return allocated


def validate_savings_allocation(
    *,
    recommendations: list[RecommendationDetail],
    roi: ROIResult,
    allocation: SavingsAllocationConfig = SAVINGS_ALLOCATION,
) -> None:
    """Guard rail: recommendation savings must never exceed the overall ROI."""
    total = sum(
        (to_decimal(r.estimated_hours_saved_per_month) for r in recommendations), Decimal(0)
    )
    ceiling = to_decimal(roi.estimated_hours_saved) + allocation.tolerance_hours
    if total <= ceiling:
        return

    message = (
        f"Recommendation hours saved ({total}) exceed the overall estimated hours saved "
        f"({roi.estimated_hours_saved})."
    )
    logger.warning(
        "savings_allocation_exceeds_roi",
        extra={
            "correlation_id": get_correlation_id(),
            "allocated_hours": str(total),
            "roi_hours": str(roi.estimated_hours_saved),
        },
    )
    if allocation.strict:
        raise ValidationError(message)


def select_quick_wins(
    recommendations: list[RecommendationDetail],
    *,
    rules: QuickWinRules = QUICK_WIN_RULES,
) -> list[QuickWin]:
    """Pick at most three genuinely quick, high-value recommendations."""
    qualifying = [
        r
        for r in recommendations
        if r.implementation_effort.value.casefold() in rules.allowed_efforts
        and r.business_impact.value.casefold() in rules.allowed_impacts
        and r.implementation_timeframe_days <= rules.max_timeframe_days
        and len(r.dependencies) <= rules.max_dependencies
    ]
    qualifying.sort(
        key=lambda r: (-float(r.estimated_monthly_value), -r.recommendation_score, r.id)
    )

    quick_wins = [
        QuickWin(
            title=r.title,
            description=r.description,
            source_recommendation_id=r.id,
            priority=r.priority,
            business_impact=r.business_impact,
            implementation_effort=r.implementation_effort,
            estimated_hours_saved_per_month=r.estimated_hours_saved_per_month,
            recommended_technologies=r.recommended_technologies,
            expected_outcome=(r.expected_benefits[0] if r.expected_benefits else r.description),
            implementation_timeframe=f"0-{r.implementation_timeframe_days} days",
            dependencies=r.dependencies,
        )
        for r in qualifying[: rules.max_results]
    ]
    logger.info(
        "quick_wins_selected",
        extra={
            "correlation_id": get_correlation_id(),
            "candidates": len(qualifying),
            "selected": len(quick_wins),
        },
    )
    return quick_wins
